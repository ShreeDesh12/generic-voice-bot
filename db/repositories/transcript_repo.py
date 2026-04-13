import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Transcript


async def append_message(
    session: AsyncSession,
    *,
    contact_id: uuid.UUID,
    role: str,
    content: str,
) -> Transcript:
    t = Transcript(contact_id=contact_id, role=role, content=content)
    session.add(t)
    await session.commit()
    return t


async def get_full_transcript(
    session: AsyncSession, contact_id: uuid.UUID
) -> list[dict]:
    result = await session.execute(
        select(Transcript)
        .where(Transcript.contact_id == contact_id)
        .order_by(Transcript.created_at.asc())
    )
    return [
        {
            "role": t.role,
            "content": t.content,
            "created_at": t.created_at.isoformat(),
        }
        for t in result.scalars().all()
    ]
