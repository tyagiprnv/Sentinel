"""
Audit logging service for restoration requests.
"""
import uuid
import re
from datetime import datetime, UTC
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.database import RestorationAuditLog, APIKey


async def log_restoration_request(
    session: AsyncSession,
    request_id: uuid.UUID,
    api_key_record: APIKey,
    redacted_text: str,
    restored_text: Optional[str] = None,
    success: bool = True,
    error_message: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> RestorationAuditLog:
    """
    Log a restoration request to the audit log.

    Args:
        session: Database session
        request_id: Unique request ID
        api_key_record: API key used for request
        redacted_text: Input text with tokens
        restored_text: Output text with PII restored
        success: Whether restoration succeeded
        error_message: Error message if failed
        ip_address: Client IP address
        user_agent: Client user agent

    Returns:
        Created audit log record
    """
    # Count tokens in redacted text
    token_count = len(re.findall(r"\[REDACTED_[a-z0-9]+\]", redacted_text))

    audit_log = RestorationAuditLog()
    audit_log.id = str(uuid.uuid4())
    audit_log.request_id = str(request_id)
    audit_log.api_key_id = str(api_key_record.id)
    audit_log.service_name = api_key_record.service_name
    audit_log.timestamp = datetime.now(UTC)
    audit_log.redacted_text = redacted_text
    audit_log.restored_text = restored_text
    audit_log.token_count = token_count
    audit_log.success = success
    audit_log.error_message = error_message
    audit_log.ip_address = ip_address
    audit_log.user_agent = user_agent

    session.add(audit_log)
    await session.commit()
    await session.refresh(audit_log)

    return audit_log


async def get_audit_logs(
    session: AsyncSession,
    service_name: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> List[RestorationAuditLog]:
    """
    Query audit logs with optional filtering.

    Args:
        session: Database session
        service_name: Filter by service name
        limit: Maximum records to return
        offset: Offset for pagination

    Returns:
        List of audit log records
    """
    stmt = select(RestorationAuditLog).order_by(desc(RestorationAuditLog.timestamp))

    if service_name:
        stmt = stmt.where(RestorationAuditLog.service_name == service_name)

    stmt = stmt.limit(limit).offset(offset)

    result = await session.execute(stmt)
    return list(result.scalars().all())
