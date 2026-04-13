import uuid

from fastapi import HTTPException, Request

from db import async_session
from db.repositories import user_repo
from db.models import User


async def get_current_user(request: Request) -> User | None:
    """Read user_id from session cookie and load the User. Returns None if not logged in."""
    user_id_str = request.session.get("user_id")
    if not user_id_str:
        return None
    try:
        user_id = uuid.UUID(user_id_str)
    except (ValueError, TypeError):
        return None
    async with async_session() as session:
        return await user_repo.get_by_id(session, user_id)


async def require_user(request: Request) -> User:
    """Same as get_current_user but raises 401 if not authenticated."""
    user = await get_current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user
