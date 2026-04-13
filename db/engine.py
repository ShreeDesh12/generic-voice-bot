import logging
import subprocess
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import config
from db.models import Base, DocumentLookup

logger = logging.getLogger(__name__)

engine = create_async_engine(config.DATABASE_URL, echo=False, future=True)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def _run_alembic_upgrade():
    """Run alembic upgrade head as a subprocess to avoid async conflicts."""
    project_root = Path(__file__).parent.parent
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(project_root),
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "DATABASE_URL": config.DATABASE_URL},
    )
    if result.returncode != 0:
        logger.error("Alembic migration failed: %s", result.stderr)
        raise RuntimeError(f"Alembic migration failed: {result.stderr}")
    logger.info("Alembic output: %s", result.stdout.strip())


async def init_db():
    """Run migrations and seed lookup data."""
    _run_alembic_upgrade()
    logger.info("Database migrations applied")

    # Seed document_lk
    async with async_session() as session:
        result = await session.execute(
            select(DocumentLookup).where(DocumentLookup.code == "resume")
        )
        if result.scalars().first() is None:
            session.add(
                DocumentLookup(code="resume", name="Resume", description="Professional resume or CV document")
            )
            await session.commit()
            logger.info("Seeded document_lk with 'resume'")
