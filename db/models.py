import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(320), nullable=False, unique=True)
    name = Column(String(255), nullable=False)
    picture_url = Column(String(2048), nullable=True)
    oauth_provider = Column(String(50), nullable=False)
    oauth_sub = Column(String(255), nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("oauth_provider", "oauth_sub", name="uq_oauth_identity"),
    )

    documents = relationship("UserDocument", back_populates="user", cascade="all, delete-orphan")
    bots = relationship("Bot", back_populates="user", cascade="all, delete-orphan")
    contacts = relationship("Contact", back_populates="user", cascade="all, delete-orphan", foreign_keys="[Contact.user_id]")


class DocumentLookup(Base):
    __tablename__ = "document_lk"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(50), nullable=False, unique=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    documents = relationship("UserDocument", back_populates="document_type")


class UserDocument(Base):
    __tablename__ = "user_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    document_type_id = Column(
        Integer, ForeignKey("document_lk.id"), nullable=False
    )
    filename = Column(String(500), nullable=False)
    content_text = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    user = relationship("User", back_populates="documents")
    document_type = relationship("DocumentLookup", back_populates="documents")
    bots = relationship("Bot", back_populates="document")


class Bot(Base):
    __tablename__ = "bots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug = Column(String(255), nullable=False, unique=True)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user_documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    title = Column(String(255), nullable=True)
    name = Column(String(255), nullable=False)
    email = Column(String(320), default="")
    phone = Column(String(50), default="")
    linkedin = Column(String(500), default="")
    gender = Column(String(20), default="unknown")
    voice_id = Column(String(100), default="")
    context = Column(Text, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    is_active = Column(String(10), nullable=False, default="active")
    created_at = Column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="bots")
    document = relationship("UserDocument", back_populates="bots")
    contacts = relationship("Contact", back_populates="bot", cascade="all, delete-orphan")


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    caller_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    bot_id = Column(
        UUID(as_uuid=True), ForeignKey("bots.id", ondelete="CASCADE"), nullable=False
    )
    session_id = Column(String(100), nullable=False, unique=True)
    contact_info = Column(JSONB, default=dict)
    status = Column(String(20), nullable=False, default="active")
    transcript_url = Column(String(1024), nullable=True)
    summary_json = Column(JSONB, nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_contacts_status_updated", "status", "updated_at"),
    )

    user = relationship("User", back_populates="contacts", foreign_keys=[user_id])
    caller = relationship("User", foreign_keys=[caller_user_id])
    bot = relationship("Bot", back_populates="contacts")
    transcripts = relationship(
        "Transcript", back_populates="contact", cascade="all, delete-orphan"
    )


class Transcript(Base):
    __tablename__ = "transcripts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contact_id = Column(
        UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False
    )
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    contact = relationship("Contact", back_populates="transcripts")
