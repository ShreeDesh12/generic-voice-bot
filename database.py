"""Backward-compatible sync shim for app.py (Streamlit).

Wraps the async DB layer so Streamlit can keep using synchronous calls.
"""
import asyncio
import logging

from db import async_session, init_db as _async_init_db
from db.repositories import bot_repo

logger = logging.getLogger(__name__)


def _run(coro):
    """Run an async coroutine from synchronous code."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


def init_db():
    _run(_async_init_db())
    logger.info("Database initialized (sync shim)")


def save_bot(
    slug: str,
    name: str,
    context: str,
    gender: str = "unknown",
    voice_id: str = "",
    email: str = "",
    phone: str = "",
    linkedin: str = "",
) -> None:
    async def _save():
        async with async_session() as session:
            await bot_repo.save_bot(
                session,
                slug=slug,
                name=name,
                context=context,
                gender=gender,
                voice_id=voice_id,
                email=email,
                phone=phone,
                linkedin=linkedin,
            )

    _run(_save())
    logger.info("Saved bot: slug=%s, name=%s, gender=%s", slug, name, gender)


def get_bot(slug: str) -> dict | None:
    async def _get():
        async with async_session() as session:
            return await bot_repo.get_bot(session, slug)

    return _run(_get())


def list_bots() -> list[dict]:
    async def _list():
        async with async_session() as session:
            return await bot_repo.list_bots(session)

    return _run(_list())
