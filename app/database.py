"""
Database configuration and models for authentication and audit logging.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, DateTime, Boolean, Integer, Text
from datetime import datetime, UTC
import uuid
from typing import AsyncGenerator, Optional
from app.config import get_settings

settings = get_settings()


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


class APIKey(Base):
    """API key model for authentication."""
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    key_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    service_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))  # Issue 12 fix
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)


class RestorationAuditLog(Base):
    """Audit log for all restoration requests."""
    __tablename__ = "restoration_audit_log"

    id: Mapped[uuid.UUID] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    request_id: Mapped[uuid.UUID] = mapped_column(
        String(36),
        nullable=False,
        index=True
    )
    api_key_id: Mapped[uuid.UUID] = mapped_column(
        String(36),
        nullable=False,
        index=True
    )
    service_name: Mapped[str] = mapped_column(String(255), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),  # Issue 12 fix
        index=True
    )
    redacted_text: Mapped[str] = mapped_column(Text, nullable=False)
    restored_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)  # IPv6 max length
    user_agent: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)


# Database engine and session factory
engine = create_async_engine(
    settings.postgres_url,
    echo=settings.postgres_echo,
    pool_size=settings.postgres_pool_size,
    max_overflow=settings.postgres_max_overflow,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for FastAPI to get database session.

    Usage:
        @app.post("/endpoint")
        async def endpoint(session: AsyncSession = Depends(get_session)):
            ...
    """
    async with async_session_maker() as session:
        yield session


async def init_database():
    """Initialize database tables (for development/testing)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
