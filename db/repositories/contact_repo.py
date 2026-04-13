import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from db.models import Bot, Contact, User

import config


async def create_contact(
    session: AsyncSession,
    *,
    bot_id: uuid.UUID,
    session_id: str,
    user_id: uuid.UUID | None = None,
    caller_user_id: uuid.UUID | None = None,
    contact_info: dict | None = None,
) -> Contact:
    contact = Contact(
        bot_id=bot_id,
        session_id=session_id,
        user_id=user_id,
        caller_user_id=caller_user_id,
        contact_info=contact_info or {},
    )
    session.add(contact)
    await session.commit()
    return contact


async def get_by_session_id(session: AsyncSession, session_id: str) -> Contact | None:
    result = await session.execute(
        select(Contact).where(Contact.session_id == session_id)
    )
    return result.scalars().first()


async def get_by_id(session: AsyncSession, contact_id: uuid.UUID) -> Contact | None:
    result = await session.execute(
        select(Contact).where(Contact.id == contact_id)
    )
    return result.scalars().first()


async def touch_updated_at(session: AsyncSession, contact_id: uuid.UUID) -> None:
    await session.execute(
        update(Contact)
        .where(Contact.id == contact_id)
        .values(updated_at=datetime.now(timezone.utc))
    )
    await session.commit()


async def get_stale_active_contacts(session: AsyncSession) -> list[Contact]:
    """Find active contacts whose updated_at is older than the drop-off timeout."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=config.DROPOFF_TIMEOUT_MINUTES)
    result = await session.execute(
        select(Contact).where(
            Contact.status == "active",
            Contact.updated_at < cutoff,
        )
    )
    return list(result.scalars().all())


async def finalize(
    session: AsyncSession,
    contact_id: uuid.UUID,
    *,
    summary_json: dict | None = None,
    transcript_url: str | None = None,
) -> None:
    values: dict = {
        "status": "finalized",
        "updated_at": datetime.now(timezone.utc),
    }
    if summary_json is not None:
        values["summary_json"] = summary_json
    if transcript_url is not None:
        values["transcript_url"] = transcript_url
    await session.execute(
        update(Contact).where(Contact.id == contact_id).values(**values)
    )
    await session.commit()


async def get_incoming_calls(session: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    """Contacts on bots owned by this user (people who called me)."""
    result = await session.execute(
        select(Contact)
        .options(joinedload(Contact.bot), joinedload(Contact.caller))
        .where(Contact.user_id == user_id, Contact.status == "finalized")
        .order_by(Contact.created_at.desc())
        .limit(20)
    )
    calls = []
    for c in result.scalars().unique().all():
        caller_name = None
        caller_email = None
        if c.caller:
            caller_name = c.caller.name
            caller_email = c.caller.email
        elif c.contact_info:
            caller_name = c.contact_info.get("name")
            caller_email = c.contact_info.get("email")
        calls.append({
            "id": str(c.id),
            "bot_name": c.bot.name if c.bot else "Unknown",
            "bot_slug": c.bot.slug if c.bot else "",
            "caller_name": caller_name or "Anonymous",
            "caller_email": caller_email or "",
            "date": c.created_at.strftime("%b %d, %Y %H:%M"),
        })
    return calls


async def get_outgoing_calls(session: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    """Contacts where this user was the caller (bots I chatted with)."""
    result = await session.execute(
        select(Contact)
        .options(joinedload(Contact.bot))
        .where(Contact.caller_user_id == user_id, Contact.status == "finalized")
        .order_by(Contact.created_at.desc())
        .limit(20)
    )
    calls = []
    for c in result.scalars().unique().all():
        calls.append({
            "id": str(c.id),
            "bot_name": c.bot.name if c.bot else "Unknown",
            "bot_slug": c.bot.slug if c.bot else "",
            "date": c.created_at.strftime("%b %d, %Y %H:%M"),
        })
    return calls
