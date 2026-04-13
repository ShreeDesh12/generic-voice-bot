import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import DocumentLookup, UserDocument


async def get_document_type_id(session: AsyncSession, code: str) -> int | None:
    """Get the document_lk id for a given code (e.g. 'resume')."""
    result = await session.execute(
        select(DocumentLookup.id).where(DocumentLookup.code == code)
    )
    return result.scalars().first()


async def save_document(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    document_type_id: int,
    filename: str,
    content_text: str,
) -> UserDocument:
    """Save a parsed document."""
    doc = UserDocument(
        user_id=user_id,
        document_type_id=document_type_id,
        filename=filename,
        content_text=content_text,
    )
    session.add(doc)
    await session.commit()
    return doc


async def list_user_documents(session: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    result = await session.execute(
        select(UserDocument)
        .where(UserDocument.user_id == user_id)
        .order_by(UserDocument.created_at.desc())
    )
    return [
        {
            "id": str(d.id),
            "filename": d.filename,
            "document_type_id": d.document_type_id,
            "created_at": d.created_at.isoformat(),
        }
        for d in result.scalars().all()
    ]
