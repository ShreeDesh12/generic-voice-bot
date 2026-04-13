import asyncio
import json
import logging

from db import async_session
from db.repositories import contact_repo, transcript_repo
from db.models import Bot, User
from email_service.sender import send_email
from email_service.templates import format_transcript_email
from llm.factory import LLMFactory
import config

from sqlalchemy import select
from sqlalchemy.orm import joinedload

logger = logging.getLogger(__name__)


async def _generate_summary(transcript_rows: list[dict]) -> dict:
    """Use the LLM to generate a conversation summary."""
    conversation = "\n".join(
        f"{r['role'].upper()}: {r['content']}" for r in transcript_rows
    )
    prompt = (
        "Summarize the following conversation between a visitor and a portfolio bot. "
        "Return a JSON object with keys: visitor_intent, key_topics (list), "
        "action_items (list), and overall_sentiment.\n\n"
        f"Conversation:\n{conversation}"
    )

    try:
        llm = LLMFactory.create(config.LLM_PROVIDER)
        raw = llm.generate(prompt=prompt, context="")
        # Strip markdown code fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Remove first line (```json) and last line (```)
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {"raw_summary": raw}
    except Exception as e:
        logger.error("Summary generation failed: %s", e)
        return {"error": str(e)}


async def _finalize_contact(contact) -> None:
    """Generate summary, send email, and mark the contact as finalized."""
    async with async_session() as session:
        # Load full transcript
        transcript_rows = await transcript_repo.get_full_transcript(session, contact.id)

        if not transcript_rows:
            await contact_repo.finalize(session, contact.id)
            return

        # Generate summary
        summary = await _generate_summary(transcript_rows)

        # Look up bot owner's email
        from db.models import Bot, User

        result = await session.execute(
            select(Bot).options(joinedload(Bot.user)).where(Bot.id == contact.bot_id)
        )
        bot = result.scalars().first()
        bot_name = bot.name if bot else "Unknown Bot"
        owner_email = bot.user.email if bot and bot.user else None

        # Build transcript URL
        transcript_url = f"/portfolio-bot/{bot.slug}/transcript/{contact.id}" if bot else None

        # Finalize contact record
        await contact_repo.finalize(
            session,
            contact.id,
            summary_json=summary,
            transcript_url=transcript_url,
        )

        # Send email to bot owner
        if owner_email:
            visitor_contact = contact.contact_info if contact.contact_info else None
            html = format_transcript_email(bot_name, transcript_rows, summary, visitor_contact)
            await send_email(
                to=owner_email,
                subject=f"Chat transcript: {bot_name}",
                html_body=html,
            )

    logger.info("Finalized contact %s", contact.id)


async def dropoff_checker_loop():
    """Background loop that checks for stale active contacts every 60 seconds."""
    logger.info("Drop-off checker started (timeout=%d min)", config.DROPOFF_TIMEOUT_MINUTES)
    while True:
        await asyncio.sleep(60)
        try:
            async with async_session() as session:
                stale = await contact_repo.get_stale_active_contacts(session)

            for contact in stale:
                try:
                    await _finalize_contact(contact)
                except Exception as e:
                    logger.error("Failed to finalize contact %s: %s", contact.id, e)
        except Exception as e:
            logger.error("Drop-off checker error: %s", e)
