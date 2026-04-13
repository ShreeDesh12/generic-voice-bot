import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import config
from db.models import Base, DocumentLookup

logger = logging.getLogger(__name__)

engine = create_async_engine(config.DATABASE_URL, echo=False, future=True)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    """Create all tables and seed lookup data."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created")

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
