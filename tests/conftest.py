"""
Pytest configuration and fixtures for testing PII redaction system.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
import fakeredis
import respx
from httpx import Response


@pytest.fixture
def mock_redis():
    """Provides a fake Redis instance for testing."""
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def mock_redactor_service(mock_redis):
    """Provides a RedactorService instance with mocked Redis."""
    from app.service import RedactorService

    service = RedactorService()
    service.db = mock_redis
    return service


@pytest.fixture
def mock_ollama_api():
    """Mock Ollama API responses using respx."""
    with respx.mock:
        yield respx


@pytest.fixture
def test_client(mock_redis):
    """Provides a FastAPI TestClient with mocked dependencies."""
    # Patch Redis in the service module before importing main
    with patch('app.service.redis.Redis', return_value=mock_redis):
        from app.main import app
        from app.service import redactor
        from app.auth import validate_api_key
        from app.database import APIKey, get_session
        from datetime import datetime, UTC
        from unittest.mock import AsyncMock
        import uuid

        # Replace the redactor's db with our mock
        redactor.db = mock_redis

        # Override the validate_api_key dependency to return a mock API key
        async def mock_validate_api_key():
            mock_key = APIKey()
            mock_key.id = str(uuid.uuid4())
            mock_key.key_hash = "test"
            mock_key.service_name = "test_service"
            mock_key.created_at = datetime.now(UTC)
            mock_key.revoked = False
            mock_key.usage_count = 0
            return mock_key

        # Mock database session
        async def mock_get_session():
            mock_session = AsyncMock()
            # Make execute and commit do nothing
            mock_session.execute = AsyncMock(return_value=AsyncMock())
            mock_session.commit = AsyncMock()
            mock_session.refresh = AsyncMock()
            yield mock_session

        app.dependency_overrides[validate_api_key] = mock_validate_api_key
        app.dependency_overrides[get_session] = mock_get_session

        return TestClient(app)


@pytest.fixture
def sample_pii_texts():
    """Sample texts containing various PII types for testing."""
    return {
        "email": "Contact me at john.doe@example.com for more information.",
        "phone": "Call me at 555-123-4567 or (555) 987-6543.",
        "name": "My name is Jane Smith and I live in New York.",
        "ssn": "My SSN is 123-45-6789.",
        "multiple": "Jane Doe's email is jane@example.com and phone is 555-1234.",
        "no_pii": "This is a clean text with no personal information.",
        "address": "I live at 123 Main Street, Springfield, IL 62701.",
    }


@pytest.fixture
def sample_redacted_text():
    """Sample redacted text with tokens."""
    return "Contact [REDACTED_a1b2] at [REDACTED_c3d4] for more information."


@pytest.fixture
def mock_llm_clean_response():
    """Mock LLM response indicating no leaks."""
    return {
        "response": '{"leaked": false, "reason": "All PII properly redacted with tokens"}'
    }


@pytest.fixture
def mock_llm_leak_response():
    """Mock LLM response indicating a leak was found."""
    return {
        "response": '{"leaked": true, "reason": "Email address john@example.com was not redacted"}'
    }


@pytest.fixture
def mock_analyzer_results():
    """Mock Presidio analyzer results."""
    from presidio_analyzer import RecognizerResult

    return [
        RecognizerResult(
            entity_type="EMAIL_ADDRESS",
            start=14,
            end=35,
            score=0.95
        ),
        RecognizerResult(
            entity_type="PERSON",
            start=5,
            end=13,
            score=0.85
        )
    ]


@pytest.fixture
def environment_vars(monkeypatch):
    """Set environment variables for testing."""
    monkeypatch.setenv("REDIS_HOST", "localhost")
    monkeypatch.setenv("REDIS_PORT", "6379")
    monkeypatch.setenv("OLLAMA_URL", "http://localhost:11434/api/generate")
    monkeypatch.setenv("OLLAMA_MODEL", "phi3")
    monkeypatch.setenv("ENABLE_API_KEY_AUTH", "false")


# Database test fixtures

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.database import Base, APIKey
from datetime import datetime, UTC
import uuid


@pytest.fixture
async def test_db_engine():
    """In-memory SQLite for tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def test_db_session(test_db_engine):
    """Test database session."""
    async_session_maker_test = async_sessionmaker(
        test_db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session_maker_test() as session:
        yield session


@pytest.fixture
async def test_api_key(test_db_session):
    """Create test API key."""
    from app.auth import generate_api_key

    raw_key, key_hash = generate_api_key()
    api_key = APIKey()
    api_key.id = str(uuid.uuid4())
    api_key.key_hash = key_hash
    api_key.service_name = "test_service"
    api_key.description = "Test key"
    api_key.revoked = False
    api_key.created_at = datetime.now(UTC)
    api_key.usage_count = 0

    test_db_session.add(api_key)
    await test_db_session.commit()
    await test_db_session.refresh(api_key)

    return {"raw_key": raw_key, "record": api_key}
