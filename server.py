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


app = FastAPI(title="My Voice", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=config.SESSION_SECRET_KEY)
app.include_router(auth_router)

BASE = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE / "templates"))

static_dir = BASE / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

_llm = None


def get_llm():
    global _llm
    if _llm is None:
        _llm = LLMFactory.create(config.LLM_PROVIDER)
    return _llm


# --- Routes ---


@app.get("/", response_class=HTMLResponse)
async def upload_page(request: Request):
    """Render the resume upload page."""
    user = await get_current_user(request)
    async with async_session() as session:
        other_bots = await bot_repo.list_bots(session)
        my_bots = []
        incoming_calls = []
        outgoing_calls = []
        if user:
            my_bots = await bot_repo.list_bots_for_user(session, user.id)
            # Remove user's active bot from the connect list
            my_slugs = {b["slug"] for b in my_bots}
            other_bots = [b for b in other_bots if b["slug"] not in my_slugs]
            incoming_calls = await contact_repo.get_incoming_calls(session, user.id)
            outgoing_calls = await contact_repo.get_outgoing_calls(session, user.id)
    return templates.TemplateResponse(
        request, "upload.html", {
            "my_bots": my_bots, "other_bots": other_bots, "user": user,
            "incoming_calls": incoming_calls, "outgoing_calls": outgoing_calls,
        }
    )


@app.post("/upload")
async def upload_resume(request: Request, resume: UploadFile = File(...), voice_gender: str = Form("auto"), bot_title: str = Form("")):
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

        # Save bot (deactivates previous bots for this user)
        await bot_repo.save_bot(
            session,
            slug=slug,
            title=bot_title.strip() or person_name,
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
    return RedirectResponse(url=f"/{slug}", status_code=303)


@app.post("/{slug}/delete")
async def delete_bot(slug: str, request: Request):
    """Soft-delete a bot. Only the owner can delete."""
    user = await require_user(request)
    async with async_session() as session:
        deleted = await bot_repo.soft_delete(session, slug, user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Bot not found or not owned by you")
    return JSONResponse({"status": "deleted", "slug": slug})


@app.post("/{slug}/activate")
async def activate_bot_route(slug: str, request: Request):
    """Activate a bot and deactivate all others."""
    user = await require_user(request)
    async with async_session() as session:
        activated = await bot_repo.activate_bot(session, slug, user.id)
    if not activated:
        raise HTTPException(status_code=404, detail="Bot not found or not owned by you")
    return JSONResponse({"status": "active", "slug": slug})


@app.post("/{slug}/deactivate")
async def deactivate_bot_route(slug: str, request: Request):
    """Deactivate a bot."""
    user = await require_user(request)
    from sqlalchemy import update as sql_update
    from db.models import Bot as BotModel
    async with async_session() as session:
        await session.execute(
            sql_update(BotModel)
            .where(BotModel.slug == slug, BotModel.user_id == user.id)
            .values(is_active="inactive")
        )
        await session.commit()
    return JSONResponse({"status": "inactive", "slug": slug})


@app.get("/{slug}", response_class=HTMLResponse)
async def bot_page(request: Request, slug: str):
    """Render the chat page for a specific bot."""
    async with async_session() as session:
        bot = await bot_repo.get_bot(session, slug)
    if bot is None:
        raise HTTPException(status_code=404, detail="Bot not found")
    user = await get_current_user(request)
    return templates.TemplateResponse(request, "bot.html", {"bot": bot, "user": user})


@app.post("/{slug}/chat")
async def chat(slug: str, request: Request):
    """Handle a chat message, store transcript, and return the LLM response."""
    caller = await get_current_user(request)
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
                caller_user_id=caller.id if caller else None,
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


@app.post("/{slug}/end-chat")
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


@app.get("/{slug}/transcript/{contact_id}", response_class=HTMLResponse)
async def view_transcript(request: Request, slug: str, contact_id: str):
    """Render a full call detail page (contact info + summary + transcript)."""
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

    # Contact info section
    contact_html = ""
    ci = contact.contact_info or {}
    if any(ci.values()):
        info_rows = ""
        if ci.get("name"):
            info_rows += f'<tr><td class="label">Name</td><td>{ci["name"]}</td></tr>'
        if ci.get("email"):
            info_rows += f'<tr><td class="label">Email</td><td><a href="mailto:{ci["email"]}">{ci["email"]}</a></td></tr>'
        if ci.get("phone"):
            info_rows += f'<tr><td class="label">Phone</td><td>{ci["phone"]}</td></tr>'
        contact_html = f'<table class="info-table">{info_rows}</table>'

    # Summary section
    summary_html = ""
    summary = contact.summary_json
    if summary:
        # Try to parse raw_summary if present
        import json as _json
        if "raw_summary" in summary:
            raw = summary["raw_summary"].strip()
            lines = [l for l in raw.split("\n") if not l.strip().startswith("```")]
            try:
                summary = _json.loads("\n".join(lines).strip())
            except _json.JSONDecodeError:
                pass

        if "raw_summary" not in summary:
            parts = ""
            if summary.get("visitor_intent"):
                parts += f'<tr><td class="label">Visitor Intent</td><td>{summary["visitor_intent"]}</td></tr>'
            if summary.get("key_topics"):
                topics = ", ".join(summary["key_topics"])
                parts += f'<tr><td class="label">Key Topics</td><td>{topics}</td></tr>'
            if summary.get("action_items"):
                items = "".join(f"<li>{i}</li>" for i in summary["action_items"])
                parts += f'<tr><td class="label">Action Items</td><td><ul>{items}</ul></td></tr>'
            if summary.get("overall_sentiment"):
                parts += f'<tr><td class="label">Sentiment</td><td>{summary["overall_sentiment"].capitalize()}</td></tr>'
            summary_html = f'<table class="info-table">{parts}</table>'
        else:
            raw_text = summary.get("raw_summary", "")
            summary_html = f'<pre class="raw-summary">{raw_text}</pre>'

    # Transcript
    messages_html = ""
    for row in rows:
        role = row["role"].capitalize()
        content = row["content"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        ts = row.get("created_at", "")
        if isinstance(ts, str) and "T" in ts:
            ts = ts.split("T")[1][:8]
        align = "flex-end" if row["role"] == "user" else "flex-start"
        bg = "var(--accent)" if row["role"] == "user" else "var(--bg-secondary)"
        messages_html += (
            f'<div style="align-self:{align};background:{bg};padding:0.75rem 1rem;'
            f'border-radius:12px;max-width:75%;white-space:pre-wrap;margin-bottom:0.5rem;">'
            f'<strong>{role}</strong> <span style="color:var(--text-secondary);font-size:0.75rem;">{ts}</span>'
            f'<br/>{content}</div>'
        )

    date_str = contact.created_at.strftime("%b %d, %Y %H:%M") if contact.created_at else ""

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Call Detail - {bot['name']}</title>
<link rel="stylesheet" href="/static/theme.css">
<script src="/static/theme.js"></script>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       background:var(--bg-primary); color:var(--text-primary); max-width:700px; margin:0 auto; padding:2rem; }}
a {{ color:var(--accent); text-decoration:none; }}
a:hover {{ text-decoration:underline; }}
h1 {{ font-size:1.3rem; margin-bottom:0.3rem; }}
.date {{ color:var(--text-muted); font-size:0.85rem; margin-bottom:1rem; }}
.top-bar {{ display:flex; align-items:center; gap:0.5rem; margin-bottom:1rem; }}
.back {{ color:var(--text-secondary); font-size:0.85rem; display:inline-block;
         padding:0.3rem 0.7rem; border:1px solid var(--border); border-radius:6px; }}
.back:hover {{ color:var(--text-primary); border-color:var(--text-primary); text-decoration:none; }}
.tabs {{ display:flex; gap:0; margin-bottom:1.2rem; }}
.tabs button {{ flex:1; padding:0.6rem; background:var(--bg-secondary); border:1px solid var(--border);
               color:var(--text-muted); font-size:0.85rem; cursor:pointer; }}
.tabs button:first-child {{ border-radius:8px 0 0 8px; }}
.tabs button:last-child {{ border-radius:0 8px 8px 0; border-left:none; }}
.tabs button:nth-child(2) {{ border-left:none; }}
.tabs button.active {{ background:var(--accent); color:#fff; border-color:var(--accent); }}
.tab-panel {{ display:none; }}
.tab-panel.active {{ display:block; }}
.info-table {{ width:100%; border-collapse:collapse; background:var(--bg-secondary); border-radius:8px; overflow:hidden; }}
.info-table td {{ padding:0.6rem 1rem; border-bottom:1px solid var(--border); }}
.info-table tr:last-child td {{ border-bottom:none; }}
.info-table .label {{ color:var(--text-secondary); font-weight:600; width:130px; vertical-align:top; }}
.info-table ul {{ margin:0; padding-left:1.2rem; }}
.raw-summary {{ background:var(--bg-secondary); padding:1rem; border-radius:8px; white-space:pre-wrap;
                font-size:0.85rem; overflow-x:auto; }}
.transcript {{ display:flex; flex-direction:column; gap:0.5rem; }}
.empty {{ color:var(--text-muted); text-align:center; padding:1.5rem; }}
</style></head><body>
<div class="top-bar">
    <a href="/" class="back">&larr; Back</a>
    <span style="flex:1;"></span>
    <button class="theme-toggle" onclick="toggleTheme()" title="Toggle theme">
        <span class="sun">&#9728;</span>
        <span class="moon">&#9790;</span>
    </button>
</div>
<h1>{bot['name']}</h1>
<div class="date">{date_str}</div>

<div class="tabs">
    <button class="active" onclick="switchTab('contact', this)">Contact</button>
    <button onclick="switchTab('summary', this)">Summary</button>
    <button onclick="switchTab('transcript', this)">Transcript</button>
</div>

<div class="tab-panel active" id="tab-contact">
    {contact_html if contact_html else '<div class="empty">No contact info provided.</div>'}
</div>

<div class="tab-panel" id="tab-summary">
    {summary_html if summary_html else '<div class="empty">No summary available.</div>'}
</div>

<div class="tab-panel" id="tab-transcript">
    <div class="transcript">{messages_html if messages_html else '<div class="empty">No messages.</div>'}</div>
</div>

<script>
function switchTab(name, btn) {{
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.tabs button').forEach(b => b.classList.remove('active'));
    document.getElementById('tab-' + name).classList.add('active');
    btn.classList.add('active');
}}
</script>
</body></html>"""
    return HTMLResponse(html)


@app.post("/{slug}/tts")
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
