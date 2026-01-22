"""
Integration tests for /suggest-policy endpoint.
"""
import pytest
import respx
from httpx import Response
import json


class TestPolicySuggestionAPI:
    """Test suite for /suggest-policy endpoint."""

    def test_suggest_policy_healthcare_endpoint(self, test_client):
        """Test /suggest-policy endpoint with healthcare text."""
        with respx.mock:
            # Mock Ollama API
            respx.post("http://ollama:11434/api/generate").mock(
                return_value=Response(
                    200,
                    json={
                        "response": json.dumps({
                            "recommended_context": "healthcare",
                            "confidence": 0.95,
                            "reasoning": "Contains PHI indicators (Patient, diagnosis)",
                            "detected_domains": ["healthcare"],
                            "alternative_contexts": [],
                            "risk_warning": None
                        })
                    }
                )
            )

            response = test_client.post(
                "/suggest-policy",
                json={"text": "Patient John Doe, diagnosis: diabetes"}
            )

            assert response.status_code == 200
            data = response.json()

            assert data["recommended_context"] == "healthcare"
            assert data["confidence"] >= 0.9
            assert "healthcare" in data["detected_domains"]
            assert isinstance(data["reasoning"], str)

    def test_suggest_policy_finance_endpoint(self, test_client):
        """Test /suggest-policy endpoint with finance text."""
        with respx.mock:
            # Mock Ollama API
            respx.post("http://ollama:11434/api/generate").mock(
                return_value=Response(
                    200,
                    json={
                        "response": json.dumps({
                            "recommended_context": "finance",
                            "confidence": 0.92,
                            "reasoning": "Contains financial PII (credit card)",
                            "detected_domains": ["finance"],
                            "alternative_contexts": [],
                            "risk_warning": None
                        })
                    }
                )
            )

            response = test_client.post(
                "/suggest-policy",
                json={"text": "Credit card payment: 4532-1234-5678-9010"}
            )

            assert response.status_code == 200
            data = response.json()

            assert data["recommended_context"] == "finance"
            assert data["confidence"] >= 0.9
            assert "finance" in data["detected_domains"]

    def test_suggest_policy_general_endpoint(self, test_client):
        """Test /suggest-policy endpoint with general text."""
        with respx.mock:
            # Mock Ollama API
            respx.post("http://ollama:11434/api/generate").mock(
                return_value=Response(
                    200,
                    json={
                        "response": json.dumps({
                            "recommended_context": "general",
                            "confidence": 0.85,
                            "reasoning": "Generic communication with basic PII",
                            "detected_domains": ["general"],
                            "alternative_contexts": [],
                            "risk_warning": None
                        })
                    }
                )
            )

            response = test_client.post(
                "/suggest-policy",
                json={"text": "Contact Sarah at sarah@example.com"}
            )

            assert response.status_code == 200
            data = response.json()

            assert data["recommended_context"] == "general"
            assert "general" in data["detected_domains"]

    def test_suggest_policy_multi_domain_endpoint(self, test_client):
        """Test /suggest-policy endpoint with multi-domain text."""
        with respx.mock:
            # Mock Ollama API
            respx.post("http://ollama:11434/api/generate").mock(
                return_value=Response(
                    200,
                    json={
                        "response": json.dumps({
                            "recommended_context": "finance",
                            "confidence": 0.88,
                            "reasoning": "Mixed healthcare and finance data. Finance has stricter thresholds.",
                            "detected_domains": ["healthcare", "finance"],
                            "alternative_contexts": ["healthcare"],
                            "risk_warning": "Text contains cross-domain PII - consider using strictest policy"
                        })
                    }
                )
            )

            response = test_client.post(
                "/suggest-policy",
                json={"text": "Patient billing: credit card ending in 1234"}
            )

            assert response.status_code == 200
            data = response.json()

            assert data["recommended_context"] in ["finance", "healthcare"]
            assert len(data["detected_domains"]) >= 2
            assert "healthcare" in data["detected_domains"]
            assert "finance" in data["detected_domains"]
            assert data["risk_warning"] is not None
            assert len(data["alternative_contexts"]) > 0

    def test_suggest_policy_empty_text_validation(self, test_client):
        """Test validation error for empty text."""
        response = test_client.post(
            "/suggest-policy",
            json={"text": ""}
        )

        # Should return validation error (422)
        assert response.status_code == 422

    def test_suggest_policy_missing_text_field(self, test_client):
        """Test validation error for missing text field."""
        response = test_client.post(
            "/suggest-policy",
            json={}
        )

        # Should return validation error (422)
        assert response.status_code == 422

    def test_suggest_policy_llm_failure_fallback(self, test_client):
        """Test graceful fallback when LLM fails."""
        with respx.mock:
            # Mock LLM failure
            respx.post("http://ollama:11434/api/generate").mock(
                return_value=Response(500, json={"error": "Server error"})
            )

            response = test_client.post(
                "/suggest-policy",
                json={"text": "Patient medical record"}
            )

            # Should still return 200 with fallback recommendation
            assert response.status_code == 200
            data = response.json()

            assert data["recommended_context"] in ["general", "healthcare", "finance"]
            assert 0.0 <= data["confidence"] <= 1.0

    def test_suggest_policy_response_schema(self, test_client):
        """Test that response matches expected schema."""
        with respx.mock:
            respx.post("http://ollama:11434/api/generate").mock(
                return_value=Response(
                    200,
                    json={
                        "response": json.dumps({
                            "recommended_context": "general",
                            "confidence": 0.8,
                            "reasoning": "Test",
                            "detected_domains": ["general"],
                            "alternative_contexts": [],
                            "risk_warning": None
                        })
                    }
                )
            )

            response = test_client.post(
                "/suggest-policy",
                json={"text": "Test text"}
            )

            assert response.status_code == 200
            data = response.json()

            # Verify all required fields
            assert "recommended_context" in data
            assert "confidence" in data
            assert "reasoning" in data
            assert "detected_domains" in data
            assert "alternative_contexts" in data
            assert "risk_warning" in data

            # Verify types
            assert isinstance(data["recommended_context"], str)
            assert isinstance(data["confidence"], float)
            assert isinstance(data["reasoning"], str)
            assert isinstance(data["detected_domains"], list)
            assert isinstance(data["alternative_contexts"], list)

    def test_suggest_policy_long_text(self, test_client):
        """Test handling of very long text."""
        long_text = "Patient data " * 1000

        with respx.mock:
            respx.post("http://ollama:11434/api/generate").mock(
                return_value=Response(
                    200,
                    json={
                        "response": json.dumps({
                            "recommended_context": "healthcare",
                            "confidence": 0.9,
                            "reasoning": "Contains patient data",
                            "detected_domains": ["healthcare"],
                            "alternative_contexts": [],
                            "risk_warning": None
                        })
                    }
                )
            )

            response = test_client.post(
                "/suggest-policy",
                json={"text": long_text}
            )

            assert response.status_code == 200

    def test_integration_suggest_then_redact(self, test_client):
        """Test workflow: suggest policy, then use it for redaction."""
        with respx.mock:
            # Mock policy suggestion
            respx.post("http://ollama:11434/api/generate").mock(
                return_value=Response(
                    200,
                    json={
                        "response": json.dumps({
                            "recommended_context": "healthcare",
                            "confidence": 0.95,
                            "reasoning": "PHI detected",
                            "detected_domains": ["healthcare"],
                            "alternative_contexts": [],
                            "risk_warning": None
                        })
                    }
                )
            )

            # Step 1: Get policy suggestion
            suggest_response = test_client.post(
                "/suggest-policy",
                json={"text": "Patient John Doe, DOB: 1990-05-15"}
            )

            assert suggest_response.status_code == 200
            suggestion = suggest_response.json()
            recommended_context = suggestion["recommended_context"]

            # Step 2: Use recommended policy for redaction
            redact_response = test_client.post(
                "/redact",
                json={
                    "text": "Patient John Doe, DOB: 1990-05-15",
                    "policy": {"context": recommended_context}
                }
            )

            assert redact_response.status_code == 200
            redaction = redact_response.json()

            # Verify policy was applied
            assert redaction["policy_applied"]["context"] == recommended_context
