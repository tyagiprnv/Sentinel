"""
Unit tests for audit logging service.
"""
import pytest
import uuid
from app.audit import log_restoration_request, get_audit_logs


@pytest.mark.asyncio
class TestAuditLogging:
    """Test audit logging functionality."""

    async def test_log_successful_restoration(self, test_db_session, test_api_key):
        """Test logging a successful restoration."""
        request_id = uuid.uuid4()
        api_key_record = test_api_key["record"]

        audit_log = await log_restoration_request(
            session=test_db_session,
            request_id=request_id,
            api_key_record=api_key_record,
            redacted_text="Contact [REDACTED_a1b2]",
            restored_text="Contact john@example.com",
            success=True,
            ip_address="192.168.1.1"
        )

        assert str(audit_log.request_id) == str(request_id)
        assert audit_log.service_name == "test_service"
        assert audit_log.token_count == 1
        assert audit_log.success is True
        assert audit_log.ip_address == "192.168.1.1"

    async def test_log_failed_restoration(self, test_db_session, test_api_key):
        """Test logging a failed restoration."""
        request_id = uuid.uuid4()
        api_key_record = test_api_key["record"]

        audit_log = await log_restoration_request(
            session=test_db_session,
            request_id=request_id,
            api_key_record=api_key_record,
            redacted_text="Contact [REDACTED_a1b2]",
            success=False,
            error_message="Policy violation"
        )

        assert audit_log.success is False
        assert audit_log.error_message == "Policy violation"
        assert audit_log.restored_text is None

    async def test_token_count_extraction(self, test_db_session, test_api_key):
        """Test that token count is correctly extracted."""
        request_id = uuid.uuid4()

        audit_log = await log_restoration_request(
            session=test_db_session,
            request_id=request_id,
            api_key_record=test_api_key["record"],
            redacted_text="[REDACTED_a1b2] and [REDACTED_c3d4] and [REDACTED_e5f6]",
            success=True
        )

        assert audit_log.token_count == 3

    async def test_token_count_no_tokens(self, test_db_session, test_api_key):
        """Test token count with no tokens."""
        request_id = uuid.uuid4()

        audit_log = await log_restoration_request(
            session=test_db_session,
            request_id=request_id,
            api_key_record=test_api_key["record"],
            redacted_text="No tokens here",
            success=True
        )

        assert audit_log.token_count == 0

    async def test_get_audit_logs(self, test_db_session, test_api_key):
        """Test querying audit logs."""
        # Create multiple log entries
        for i in range(5):
            await log_restoration_request(
                session=test_db_session,
                request_id=uuid.uuid4(),
                api_key_record=test_api_key["record"],
                redacted_text=f"Test {i}",
                success=True
            )

        # Query logs
        logs = await get_audit_logs(
            session=test_db_session,
            limit=10
        )

        assert len(logs) == 5

    async def test_get_audit_logs_with_filter(self, test_db_session, test_api_key):
        """Test filtering audit logs by service name."""
        # Create logs
        for i in range(3):
            await log_restoration_request(
                session=test_db_session,
                request_id=uuid.uuid4(),
                api_key_record=test_api_key["record"],
                redacted_text=f"Test {i}",
                success=True
            )

        # Query with filter
        logs = await get_audit_logs(
            session=test_db_session,
            service_name="test_service",
            limit=10
        )

        assert len(logs) == 3
        assert all(log.service_name == "test_service" for log in logs)

    async def test_get_audit_logs_pagination(self, test_db_session, test_api_key):
        """Test audit log pagination."""
        # Create 10 logs
        for i in range(10):
            await log_restoration_request(
                session=test_db_session,
                request_id=uuid.uuid4(),
                api_key_record=test_api_key["record"],
                redacted_text=f"Test {i}",
                success=True
            )

        # Get first 5
        logs_page1 = await get_audit_logs(
            session=test_db_session,
            limit=5,
            offset=0
        )

        # Get next 5
        logs_page2 = await get_audit_logs(
            session=test_db_session,
            limit=5,
            offset=5
        )

        assert len(logs_page1) == 5
        assert len(logs_page2) == 5
        # Ensure they're different logs
        page1_ids = {log.id for log in logs_page1}
        page2_ids = {log.id for log in logs_page2}
        assert page1_ids.isdisjoint(page2_ids)
