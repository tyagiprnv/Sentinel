"""
Unit tests for authentication service.
"""
import pytest
from app.auth import generate_api_key, hash_api_key


class TestAPIKeyGeneration:
    """Test API key generation."""

    def test_generate_api_key_format(self):
        """Test that generated API keys have correct format."""
        raw_key, key_hash = generate_api_key()

        # Raw key should be 64 hex characters
        assert len(raw_key) == 64
        assert all(c in "0123456789abcdef" for c in raw_key)

        # Hash should be 64 hex characters (SHA-256)
        assert len(key_hash) == 64
        assert all(c in "0123456789abcdef" for c in key_hash)

    def test_generate_api_key_uniqueness(self):
        """Test that each generated key is unique."""
        key1, hash1 = generate_api_key()
        key2, hash2 = generate_api_key()

        assert key1 != key2
        assert hash1 != hash2

    def test_hash_api_key_deterministic(self):
        """Test that hashing is deterministic."""
        raw_key = "test_key_12345"

        hash1 = hash_api_key(raw_key)
        hash2 = hash_api_key(raw_key)

        assert hash1 == hash2

    def test_hash_api_key_different_inputs(self):
        """Test that different keys produce different hashes."""
        hash1 = hash_api_key("test_key_1")
        hash2 = hash_api_key("test_key_2")

        assert hash1 != hash2


@pytest.mark.asyncio
class TestAPIKeyValidation:
    """Test API key validation."""

    async def test_api_key_storage(self, test_db_session, test_api_key):
        """Test that API keys are stored correctly in database."""
        api_key_record = test_api_key["record"]

        assert api_key_record.service_name == "test_service"
        assert api_key_record.description == "Test key"
        assert api_key_record.revoked is False
        assert api_key_record.usage_count == 0

    async def test_api_key_hash_matching(self, test_db_session, test_api_key):
        """Test that raw key hashes to stored hash."""
        raw_key = test_api_key["raw_key"]
        api_key_record = test_api_key["record"]

        computed_hash = hash_api_key(raw_key)
        assert computed_hash == api_key_record.key_hash
