import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import User


async def find_or_create_from_oauth(
    session: AsyncSession,
    *,
    provider: str,
    sub: str,
    email: str,
    name: str,
    picture_url: str | None = None,
) -> User:
    """Find an existing user by OAuth identity or create a new one."""
    result = await session.execute(
        select(User).where(User.oauth_provider == provider, User.oauth_sub == sub)
    )
    user = result.scalars().first()
    if user is not None:
        user.email = email
        user.name = name
        user.picture_url = picture_url
        await session.commit()
        return user

    user = User(
        id=uuid.uuid4(),
        email=email,
        name=name,
        picture_url=picture_url,
        oauth_provider=provider,
        oauth_sub=sub,
    )
    session.add(user)
    await session.commit()
    return user


async def get_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalars().first()
