import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from db.models import Bot


async def save_bot(
    session: AsyncSession,
    *,
    slug: str,
    name: str,
    context: str,
    title: str = "",
    gender: str = "unknown",
    voice_id: str = "",
    email: str = "",
    phone: str = "",
    linkedin: str = "",
    user_id: uuid.UUID | None = None,
    document_id: uuid.UUID | None = None,
) -> Bot:
    """Create a new bot. Deactivates all other bots for this user and auto-increments version."""
    version = 1
    if user_id:
        # Deactivate all existing bots for this user
        await session.execute(
            update(Bot)
            .where(Bot.user_id == user_id, Bot.deleted_at.is_(None))
            .values(is_active="inactive")
        )
        # Get next version number
        result = await session.execute(
            select(func.coalesce(func.max(Bot.version), 0))
            .where(Bot.user_id == user_id)
        )
        version = result.scalar() + 1

    bot = Bot(
        slug=slug,
        title=title or name,
        name=name,
        context=context,
        gender=gender,
        voice_id=voice_id,
        email=email,
        phone=phone,
        linkedin=linkedin,
        user_id=user_id,
        document_id=document_id,
        version=version,
        is_active="active",
    )
    session.add(bot)
    await session.commit()
    return bot


async def get_bot(session: AsyncSession, slug: str) -> dict | None:
    """Load a bot by slug. Excludes soft-deleted."""
    result = await session.execute(
        select(Bot)
        .options(joinedload(Bot.user))
        .where(Bot.slug == slug, Bot.deleted_at.is_(None))
    )
    bot = result.scalars().first()
    if bot is None:
        return None
    return {
        "id": str(bot.id),
        "slug": bot.slug,
        "title": bot.title or bot.name,
        "name": bot.name,
        "email": bot.email,
        "phone": bot.phone,
        "linkedin": bot.linkedin,
        "gender": bot.gender,
        "voice_id": bot.voice_id,
        "context": bot.context,
        "version": bot.version,
        "is_active": bot.is_active,
        "user_id": str(bot.user_id) if bot.user_id else None,
        "picture_url": bot.user.picture_url if bot.user else None,
        "created_at": bot.created_at.isoformat(),
    }


async def list_bots(session: AsyncSession) -> list[dict]:
    """List all active (not deleted, is_active) bots for the Connect page."""
    result = await session.execute(
        select(Bot)
        .where(Bot.deleted_at.is_(None), Bot.is_active == "active")
        .order_by(Bot.created_at.desc())
    )
    return [
        {
            "slug": b.slug,
            "title": b.title or b.name,
            "name": b.name,
            "email": b.email,
            "gender": b.gender,
            "user_id": str(b.user_id) if b.user_id else None,
            "created_at": b.created_at.isoformat(),
        }
        for b in result.scalars().all()
    ]


async def list_bots_for_user(session: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    """List all bots (active + inactive) belonging to a user."""
    result = await session.execute(
        select(Bot)
        .where(Bot.user_id == user_id, Bot.deleted_at.is_(None))
        .order_by(Bot.created_at.desc())
    )
    return [
        {
            "slug": b.slug,
            "title": b.title or b.name,
            "name": b.name,
            "email": b.email,
            "gender": b.gender,
            "version": b.version,
            "is_active": b.is_active,
            "created_at": b.created_at.isoformat(),
        }
        for b in result.scalars().all()
    ]


async def slug_exists(session: AsyncSession, slug: str) -> bool:
    result = await session.execute(select(Bot.id).where(Bot.slug == slug))
    return result.scalars().first() is not None


async def soft_delete(session: AsyncSession, slug: str, user_id: uuid.UUID) -> bool:
    result = await session.execute(
        update(Bot)
        .where(Bot.slug == slug, Bot.user_id == user_id, Bot.deleted_at.is_(None))
        .values(deleted_at=datetime.now(timezone.utc))
    )
    await session.commit()
    return result.rowcount > 0


async def activate_bot(session: AsyncSession, slug: str, user_id: uuid.UUID) -> bool:
    """Activate a bot and deactivate all others for this user."""
    # Deactivate all
    await session.execute(
        update(Bot)
        .where(Bot.user_id == user_id, Bot.deleted_at.is_(None))
        .values(is_active="inactive")
    )
    # Activate the selected one
    result = await session.execute(
        update(Bot)
        .where(Bot.slug == slug, Bot.user_id == user_id, Bot.deleted_at.is_(None))
        .values(is_active="active")
    )
    await session.commit()
    return result.rowcount > 0
