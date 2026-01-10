"""
Authentication service for API key validation.
"""
import hashlib
import secrets
import uuid
from typing import Tuple
from datetime import datetime, UTC
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, Security, Depends
from fastapi.security import APIKeyHeader
from app.database import APIKey, get_session
from app.config import get_settings

settings = get_settings()
api_key_header = APIKeyHeader(name=settings.api_key_header, auto_error=True)


def generate_api_key() -> Tuple[str, str]:
    """
    Generate a new API key.

    Returns:
        Tuple of (raw_key, key_hash)
        - raw_key: 32-byte hex string to give to client (show once!)
        - key_hash: SHA-256 hash to store in database
    """
    raw_key = secrets.token_hex(32)  # 64 characters
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    return raw_key, key_hash


def hash_api_key(raw_key: str) -> str:
    """Hash API key for database lookup."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


async def validate_api_key(
    api_key: str = Security(api_key_header),
    session: AsyncSession = Depends(get_session)
) -> APIKey:
    """
    FastAPI dependency to validate API key from header.

    Usage:
        @app.post("/protected")
        async def protected_endpoint(api_key_record: APIKey = Depends(validate_api_key)):
            service_name = api_key_record.service_name
            ...

    Args:
        api_key: Raw API key from X-API-Key header
        session: Database session

    Returns:
        APIKey record from database

    Raises:
        HTTPException(401): If key is invalid or revoked
    """
    if not settings.enable_api_key_auth:
        # Auth disabled for testing - create mock key
        mock_key = APIKey()
        mock_key.id = str(uuid.uuid4())
        mock_key.key_hash = "test"
        mock_key.service_name = "test_service"
        mock_key.created_at = datetime.now(UTC)
        mock_key.revoked = False
        mock_key.usage_count = 0
        return mock_key

    key_hash = hash_api_key(api_key)

    # Look up key in database
    stmt = select(APIKey).where(APIKey.key_hash == key_hash)
    result = await session.execute(stmt)
    api_key_record = result.scalar_one_or_none()

    if not api_key_record:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )

    if api_key_record.revoked:
        raise HTTPException(
            status_code=401,
            detail="API key has been revoked"
        )

    # Update last_used_at and usage_count
    await session.execute(
        update(APIKey)
        .where(APIKey.id == api_key_record.id)
        .values(
            last_used_at=datetime.now(UTC),
            usage_count=APIKey.usage_count + 1
        )
    )
    await session.commit()

    return api_key_record
