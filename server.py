import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slugify import slugify
from starlette.middleware.sessions import SessionMiddleware

import config
from auth.dependencies import get_current_user, require_user
from auth.oauth import router as auth_router
from content.parser import ContentParser
from db import async_session, init_db
from db.repositories import bot_repo, contact_repo, document_repo, transcript_repo
from llm.factory import LLMFactory
from tasks.dropoff_checker import dropoff_checker_loop
from voice.gender import detect_gender, voice_id_for_gender
from voice.speaker import VoiceSpeaker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("Database initialized")
    checker_task = asyncio.create_task(dropoff_checker_loop())
    yield
    checker_task.cancel()


app = FastAPI(title="Portfolio Voice Bot", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=config.SESSION_SECRET_KEY)
app.include_router(auth_router)

BASE = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE / "templates"))

static_dir = BASE / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/portfolio-bot/static", StaticFiles(directory=str(static_dir)), name="static")

_llm = None


def get_llm():
    global _llm
    if _llm is None:
        _llm = LLMFactory.create(config.LLM_PROVIDER)
    return _llm


# --- Routes ---


@app.get("/portfolio-bot/", response_class=HTMLResponse)
async def upload_page(request: Request):
    """Render the resume upload page."""
    user = await get_current_user(request)
    async with async_session() as session:
        all_bots = await bot_repo.list_bots(session)
    if user:
        uid = str(user.id)
        my_bots = [b for b in all_bots if b.get("user_id") == uid]
        other_bots = [b for b in all_bots if b.get("user_id") != uid]
    else:
        my_bots = []
        other_bots = all_bots
    return templates.TemplateResponse(
        request, "upload.html", {"my_bots": my_bots, "other_bots": other_bots, "user": user}
    )


@app.post("/portfolio-bot/upload")
async def upload_resume(request: Request, resume: UploadFile = File(...), voice_gender: str = Form("auto")):
    """Accept a resume upload, parse it, create a bot, and redirect."""
    user = await require_user(request)

    filename = resume.filename or "file"

    async def _error_response(error_msg, status=400):
        async with async_session() as session:
            all_bots = await bot_repo.list_bots(session)
        uid = str(user.id)
        return templates.TemplateResponse(
            request, "upload.html",
            {"error": error_msg, "my_bots": [b for b in all_bots if b.get("user_id") == uid],
             "other_bots": [b for b in all_bots if b.get("user_id") != uid], "user": user},
            status_code=status,
        )

    if not filename.lower().endswith((".pdf", ".docx")):
        return await _error_response("Please upload a PDF or DOCX file.")

    try:
        contents = await resume.read()
        file_obj = BytesIO(contents)
        file_obj.filename = filename
        file_obj.name = filename
        text, contacts, person_name = ContentParser.parse_resume(file_obj)
    except ValueError as e:
        return await _error_response(str(e))
    except Exception as e:
        logger.error("Resume parsing failed: %s", e)
        return await _error_response(f"Failed to parse resume: {e}", 500)

    async with async_session() as session:
        # Generate unique slug
        slug = slugify(person_name) if person_name != "Unknown" else slugify(filename.rsplit(".", 1)[0])
        if await bot_repo.slug_exists(session, slug):
            counter = 2
            while await bot_repo.slug_exists(session, f"{slug}-{counter}"):
                counter += 1
            slug = f"{slug}-{counter}"

        # Detect gender — use user selection, fall back to auto-detect
        if voice_gender in ("female", "male"):
            gender = voice_gender
        else:
            first_name = person_name.split()[0] if person_name != "Unknown" else ""
            gender = detect_gender(first_name)
        voice_id = voice_id_for_gender(gender)

        # Save document
        doc_type_id = await document_repo.get_document_type_id(session, "resume")
        doc = await document_repo.save_document(
            session,
            user_id=user.id,
            document_type_id=doc_type_id,
            filename=filename,
            content_text=text,
        )

        # Save bot
        await bot_repo.save_bot(
            session,
            slug=slug,
            name=person_name,
            context=text,
            gender=gender,
            voice_id=voice_id,
            email=contacts.get("email", ""),
            phone=contacts.get("phone", ""),
            linkedin=contacts.get("linkedin", ""),
            user_id=user.id,
            document_id=doc.id,
        )

    logger.info("Created bot: slug=%s, name=%s, gender=%s, voice=%s", slug, person_name, gender, voice_id)
    return RedirectResponse(url=f"/portfolio-bot/{slug}", status_code=303)


@app.post("/portfolio-bot/{slug}/delete")
async def delete_bot(slug: str, request: Request):
    """Soft-delete a bot. Only the owner can delete."""
    user = await require_user(request)
    async with async_session() as session:
        deleted = await bot_repo.soft_delete(session, slug, user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Bot not found or not owned by you")
    return RedirectResponse(url="/portfolio-bot/", status_code=303)


@app.get("/portfolio-bot/{slug}", response_class=HTMLResponse)
async def bot_page(request: Request, slug: str):
    """Render the chat page for a specific bot."""
    async with async_session() as session:
        bot = await bot_repo.get_bot(session, slug)
    if bot is None:
        raise HTTPException(status_code=404, detail="Bot not found")
    user = await get_current_user(request)
    return templates.TemplateResponse(request, "bot.html", {"bot": bot, "user": user})


@app.post("/portfolio-bot/{slug}/chat")
async def chat(slug: str, request: Request):
    """Handle a chat message, store transcript, and return the LLM response."""
    async with async_session() as session:
        bot = await bot_repo.get_bot(session, slug)
    if bot is None:
        raise HTTPException(status_code=404, detail="Bot not found")

    body = await request.json()
    message = body.get("message", "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Empty message")

    session_id = body.get("session_id")
    bot_uuid = uuid.UUID(bot["id"])

    async with async_session() as session:
        # Find or create contact for this chat session
        if session_id:
            contact = await contact_repo.get_by_session_id(session, session_id)
        else:
            contact = None

        if contact is None:
            session_id = str(uuid.uuid4())
            contact = await contact_repo.create_contact(
                session,
                bot_id=bot_uuid,
                session_id=session_id,
                user_id=uuid.UUID(bot["user_id"]) if bot.get("user_id") else None,
            )

        # Store user message
        await transcript_repo.append_message(
            session, contact_id=contact.id, role="user", content=message
        )

    # Generate LLM response
    contact_details = {
        k: v
        for k, v in {
            "email": bot["email"],
            "phone": bot["phone"],
            "linkedin": bot["linkedin"],
        }.items()
        if v
    }

    try:
        llm = get_llm()
        response_text = llm.generate_portfolio(
            prompt=message,
            context=bot["context"],
            contact_details=contact_details,
        )
    except Exception as e:
        logger.error("LLM error for bot %s: %s", slug, e)
        raise HTTPException(status_code=500, detail=f"LLM Error: {e}")

    # Store assistant response and update timestamp
    async with async_session() as session:
        await transcript_repo.append_message(
            session, contact_id=contact.id, role="assistant", content=response_text
        )
        await contact_repo.touch_updated_at(session, contact.id)

    return JSONResponse({"response": response_text, "session_id": session_id})


@app.post("/portfolio-bot/{slug}/end-chat")
async def end_chat(slug: str, request: Request):
    """Explicitly finalize a chat session."""
    body = await request.json()
    session_id = body.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")

    contact_info = body.get("contact_info")

    async with async_session() as session:
        contact = await contact_repo.get_by_session_id(session, session_id)
        if contact is None or contact.status == "finalized":
            return JSONResponse({"status": "already_finalized"})

        # Save visitor contact info if provided
        if contact_info and isinstance(contact_info, dict):
            from sqlalchemy import update as sql_update
            from db.models import Contact
            await session.execute(
                sql_update(Contact)
                .where(Contact.id == contact.id)
                .values(contact_info=contact_info)
            )
            await session.commit()

        from tasks.dropoff_checker import _finalize_contact

    await _finalize_contact(contact)
    return JSONResponse({"status": "finalized"})


@app.get("/portfolio-bot/{slug}/transcript/{contact_id}", response_class=HTMLResponse)
async def view_transcript(request: Request, slug: str, contact_id: str):
    """Render a full transcript page (linked from email)."""
    try:
        cid = uuid.UUID(contact_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid contact ID")

    async with async_session() as session:
        bot = await bot_repo.get_bot(session, slug)
        if bot is None:
            raise HTTPException(status_code=404, detail="Bot not found")

        contact = await contact_repo.get_by_id(session, cid)
        if contact is None:
            raise HTTPException(status_code=404, detail="Transcript not found")

        rows = await transcript_repo.get_full_transcript(session, cid)

    messages_html = ""
    for row in rows:
        role = row["role"].capitalize()
        content = row["content"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        align = "flex-end" if row["role"] == "user" else "flex-start"
        bg = "#3b82f6" if row["role"] == "user" else "#1e293b"
        messages_html += (
            f'<div style="align-self:{align};background:{bg};padding:0.75rem 1rem;'
            f'border-radius:12px;max-width:75%;white-space:pre-wrap;margin-bottom:0.5rem;">'
            f"<strong>{role}:</strong> {content}</div>"
        )

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Transcript - {bot['name']}</title>
<style>
body {{ font-family: -apple-system, sans-serif; background:#0f172a; color:#e2e8f0;
       max-width:700px; margin:0 auto; padding:2rem; }}
h1 {{ font-size:1.4rem; }}
.transcript {{ display:flex; flex-direction:column; gap:0.5rem; }}
</style></head><body>
<h1>Transcript: {bot['name']}</h1>
<div class="transcript">{messages_html}</div>
</body></html>"""
    return HTMLResponse(html)


@app.post("/portfolio-bot/{slug}/tts")
async def tts(slug: str, request: Request):
    """Convert text to speech and return audio bytes."""
    async with async_session() as session:
        bot = await bot_repo.get_bot(session, slug)
    if bot is None:
        raise HTTPException(status_code=404, detail="Bot not found")

    body = await request.json()
    text = body.get("text", "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Empty text")

    try:
        speaker = VoiceSpeaker(voice_id=bot["voice_id"], gender=bot.get("gender"))
        audio_bytes = speaker.speak(text)
    except Exception as e:
        logger.error("TTS error for bot %s: %s", slug, e)
        raise HTTPException(status_code=500, detail=f"TTS Error: {e}")

    return Response(content=audio_bytes, media_type="audio/mpeg")
