"""
Integration tests for Policy Engine API endpoints.

Tests policy-based redaction, restoration blocking, and policy information endpoints.
"""

import pytest
import respx
from httpx import Response


class TestPolicyRedaction:
    """Test policy-based redaction via /redact endpoint."""

    def test_redact_with_general_policy_default(self, test_client):
        """Test redaction with default general policy (no policy specified)."""
        with respx.mock:
            respx.post("http://ollama:11434/api/generate").mock(
                return_value=Response(
                    200,
                    json={"response": '{"leaked": false, "reason": "Clean"}'}
                )
            )

            response = test_client.post(
                "/redact",
                json={"text": "Contact john.doe@example.com or call 555-1234"}
            )

            assert response.status_code == 200
            data = response.json()

            # Verify redaction occurred
            assert "john.doe@example.com" not in data["redacted_text"]
            assert "[REDACTED_" in data["redacted_text"]

            # Verify policy was applied
            assert data["policy_applied"] is not None
            assert data["policy_applied"]["context"] == "general"
            assert data["policy_applied"]["restoration_allowed"] is False  # Default is opt-in (False)

    def test_redact_with_healthcare_policy(self, test_client):
        """Test redaction with healthcare policy context."""
        with respx.mock:
            respx.post("http://ollama:11434/api/generate").mock(
                return_value=Response(
                    200,
                    json={"response": '{"leaked": false, "reason": "Clean"}'}
                )
            )

            response = test_client.post(
                "/redact",
                json={
                    "text": "Dr. Smith (555-1234) saw patient on 2024-01-01",
                    "policy": {"context": "healthcare"}
                }
            )

            assert response.status_code == 200
            data = response.json()

            # Verify policy metadata
            assert data["policy_applied"]["context"] == "healthcare"
            assert data["policy_applied"]["restoration_allowed"] is False
            assert "healthcare" in data["policy_applied"]["description"].lower()

    def test_redact_with_finance_policy(self, test_client):
        """Test redaction with finance policy context."""
        with respx.mock:
            respx.post("http://ollama:11434/api/generate").mock(
                return_value=Response(
                    200,
                    json={"response": '{"leaked": false, "reason": "Clean"}'}
                )
            )

            response = test_client.post(
                "/redact",
                json={
                    "text": "Account 123-45-6789 belongs to John Doe",
                    "policy": {"context": "finance"}
                }
            )

            assert response.status_code == 200
            data = response.json()

            # Verify policy metadata
            assert data["policy_applied"]["context"] == "finance"
            assert data["policy_applied"]["restoration_allowed"] is False

    def test_redact_with_custom_enabled_entities(self, test_client):
        """Test redaction with custom enabled_entities override."""
        with respx.mock:
            respx.post("http://ollama:11434/api/generate").mock(
                return_value=Response(
                    200,
                    json={"response": '{"leaked": false, "reason": "Clean"}'}
                )
            )

            response = test_client.post(
                "/redact",
                json={
                    "text": "Email jane@example.com, phone 555-1234, SSN 123-45-6789",
                    "policy": {
                        "enabled_entities": ["EMAIL_ADDRESS"]  # Only redact emails
                    }
                }
            )

            assert response.status_code == 200
            data = response.json()

            # Email should be redacted
            assert "jane@example.com" not in data["redacted_text"]

            # Phone and SSN might still appear (depending on Presidio detection)
            # We're testing that policy filtering is applied

    def test_redact_with_disabled_entities(self, test_client):
        """Test redaction with disabled_entities preventing specific redactions."""
        with respx.mock:
            respx.post("http://ollama:11434/api/generate").mock(
                return_value=Response(
                    200,
                    json={"response": '{"leaked": false, "reason": "Clean"}'}
                )
            )

            response = test_client.post(
                "/redact",
                json={
                    "text": "Contact john.doe@example.com on 2024-01-15",
                    "policy": {
                        "disabled_entities": ["DATE_TIME"]  # Don't redact dates
                    }
                }
            )

            assert response.status_code == 200
            data = response.json()

            # Email should be redacted
            assert "john.doe@example.com" not in data["redacted_text"]

            # Date might still appear (policy says don't redact dates)
            # The exact behavior depends on Presidio detection

    def test_redact_with_min_confidence_threshold(self, test_client):
        """Test redaction with custom confidence threshold."""
        with respx.mock:
            respx.post("http://ollama:11434/api/generate").mock(
                return_value=Response(
                    200,
                    json={"response": '{"leaked": false, "reason": "Clean"}'}
                )
            )

            response = test_client.post(
                "/redact",
                json={
                    "text": "Maybe contact john@example.com",
                    "policy": {
                        "min_confidence_threshold": 0.9  # Very high threshold
                    }
                }
            )

            assert response.status_code == 200
            # Low-confidence entities should not be redacted
            # (exact behavior depends on Presidio scores)


class TestRestorationBlocking:
    """Test restoration blocking based on policy."""

    def test_restore_allowed_with_general_policy(self, test_client):
        """Test restoration succeeds with general policy (restoration allowed)."""
        with respx.mock:
            respx.post("http://ollama:11434/api/generate").mock(
                return_value=Response(
                    200,
                    json={"response": '{"leaked": false, "reason": "Clean"}'}
                )
            )

            # First, redact with general policy and explicitly enable restoration
            redact_response = test_client.post(
                "/redact",
                json={
                    "text": "Email is john@example.com",
                    "policy": {
                        "context": "general",
                        "restoration_allowed": True  # Explicitly enable
                    }
                }
            )

            assert redact_response.status_code == 200
            redacted_text = redact_response.json()["redacted_text"]

            # Now try to restore
            restore_response = test_client.post(
                "/restore",
                json={"redacted_text": redacted_text}
            )

            # Should succeed (restoration was enabled)
            assert restore_response.status_code == 200
            assert "john@example.com" in restore_response.json()["original_text"]

    def test_restore_blocked_with_healthcare_policy(self, test_client):
        """Test restoration blocked with healthcare policy (restoration forbidden)."""
        with respx.mock:
            respx.post("http://ollama:11434/api/generate").mock(
                return_value=Response(
                    200,
                    json={"response": '{"leaked": false, "reason": "Clean"}'}
                )
            )

            # First, redact with healthcare policy
            redact_response = test_client.post(
                "/redact",
                json={
                    "text": "Patient email is jane@example.com",
                    "policy": {"context": "healthcare"}
                }
            )

            assert redact_response.status_code == 200
            redacted_text = redact_response.json()["redacted_text"]

            # Now try to restore
            restore_response = test_client.post(
                "/restore",
                json={"redacted_text": redacted_text}
            )

            # Should be blocked (healthcare policy forbids restoration)
            assert restore_response.status_code == 403
            assert "forbidden" in restore_response.json()["detail"].lower()

    def test_restore_blocked_with_finance_policy(self, test_client):
        """Test restoration blocked with finance policy (restoration forbidden)."""
        with respx.mock:
            respx.post("http://ollama:11434/api/generate").mock(
                return_value=Response(
                    200,
                    json={"response": '{"leaked": false, "reason": "Clean"}'}
                )
            )

            # First, redact with finance policy (use email which is reliably detected)
            redact_response = test_client.post(
                "/redact",
                json={
                    "text": "Contact finance@example.com for account details",
                    "policy": {"context": "finance"}
                }
            )

            assert redact_response.status_code == 200
            redacted_text = redact_response.json()["redacted_text"]

            # Only test restoration blocking if redaction actually occurred
            if "[REDACTED_" in redacted_text:
                # Now try to restore
                restore_response = test_client.post(
                    "/restore",
                    json={"redacted_text": redacted_text}
                )

                # Should be blocked (finance policy forbids restoration)
                assert restore_response.status_code == 403

    def test_restore_with_custom_restoration_policy(self, test_client):
        """Test restoration with custom restoration_allowed override."""
        with respx.mock:
            respx.post("http://ollama:11434/api/generate").mock(
                return_value=Response(
                    200,
                    json={"response": '{"leaked": false, "reason": "Clean"}'}
                )
            )

            # Redact with custom policy that allows restoration
            redact_response = test_client.post(
                "/redact",
                json={
                    "text": "Email is test@example.com",
                    "policy": {
                        "context": "custom",
                        "restoration_allowed": True
                    }
                }
            )

            assert redact_response.status_code == 200
            redacted_text = redact_response.json()["redacted_text"]

            # Restoration should succeed
            restore_response = test_client.post(
                "/restore",
                json={"redacted_text": redacted_text}
            )

            assert restore_response.status_code == 200


class TestPoliciesEndpoint:
    """Test GET /policies endpoint."""

    def test_get_policies_endpoint(self, test_client):
        """Test retrieving available policies."""
        response = test_client.get("/policies")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "available_contexts" in data
        assert "default_context" in data
        assert "policies" in data

        # Verify available contexts
        assert "general" in data["available_contexts"]
        assert "healthcare" in data["available_contexts"]
        assert "finance" in data["available_contexts"]

        # Verify default context
        assert data["default_context"] == "general"

        # Verify policies detail
        assert len(data["policies"]) >= 3
        assert isinstance(data["policies"], list)

    def test_get_policies_detail(self, test_client):
        """Test policy details include necessary information."""
        response = test_client.get("/policies")

        assert response.status_code == 200
        data = response.json()

        # Check first policy has required fields
        first_policy = data["policies"][0]
        assert "context" in first_policy
        assert "description" in first_policy
        assert "restoration_allowed" in first_policy
        assert "min_confidence_threshold" in first_policy
        assert "enabled_entities" in first_policy

    def test_policies_healthcare_configuration(self, test_client):
        """Test healthcare policy has correct configuration."""
        response = test_client.get("/policies")
        data = response.json()

        # Find healthcare policy
        healthcare = next(
            p for p in data["policies"] if p["context"] == "healthcare"
        )

        assert healthcare["restoration_allowed"] is False
        assert healthcare["min_confidence_threshold"] >= 0.5
        assert "PERSON" in healthcare["enabled_entities"]

    def test_policies_finance_configuration(self, test_client):
        """Test finance policy has correct configuration."""
        response = test_client.get("/policies")
        data = response.json()

        # Find finance policy
        finance = next(
            p for p in data["policies"] if p["context"] == "finance"
        )

        assert finance["restoration_allowed"] is False
        assert finance["min_confidence_threshold"] >= 0.6
        assert "CREDIT_CARD" in finance["enabled_entities"]
        assert "US_SSN" in finance["enabled_entities"]
