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

        # Replace the redactor's db with our mock
        redactor.db = mock_redis

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
