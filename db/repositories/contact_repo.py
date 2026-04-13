import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Contact

import config


async def create_contact(
    session: AsyncSession,
    *,
    bot_id: uuid.UUID,
    session_id: str,
    user_id: uuid.UUID | None = None,
    contact_info: dict | None = None,
) -> Contact:
    contact = Contact(
        bot_id=bot_id,
        session_id=session_id,
        user_id=user_id,
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
