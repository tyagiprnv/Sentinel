"""
Unit tests for PolicyRecommendationService.
"""
import pytest
import respx
from httpx import Response
import json
from app.policy_recommendation import PolicyRecommendationService


class TestPolicyRecommendationService:
    """Test suite for PolicyRecommendationService."""

    @pytest.fixture
    def recommendation_service(self, monkeypatch):
        """Create a PolicyRecommendationService instance with test settings."""
        # Set test environment variables
        monkeypatch.setenv("OLLAMA_URL", "http://ollama:11434/api/generate")
        monkeypatch.setenv("OLLAMA_MODEL", "phi3")

        # Reload settings
        from app.config import reload_settings
        reload_settings()

        return PolicyRecommendationService()

    @pytest.mark.asyncio
    async def test_suggest_policy_healthcare(self, recommendation_service):
        """Test policy suggestion for healthcare text."""
        text = "Patient John Doe, DOB: 1990-05-15, diagnosis: hypertension"

        with respx.mock:
            # Mock LLM response for healthcare text
            respx.post("http://ollama:11434/api/generate").mock(
                return_value=Response(
                    200,
                    json={
                        "response": json.dumps({
                            "recommended_context": "healthcare",
                            "confidence": 0.95,
                            "reasoning": "Contains clear PHI indicators (Patient, DOB, diagnosis). HIPAA compliance required.",
                            "detected_domains": ["healthcare"],
                            "alternative_contexts": [],
                            "risk_warning": None
                        })
                    }
                )
            )

            result = await recommendation_service.suggest_policy(text)

            assert result["recommended_context"] == "healthcare"
            assert result["confidence"] >= 0.9
            assert "healthcare" in result["detected_domains"]
            assert "PHI" in result["reasoning"] or "HIPAA" in result["reasoning"]

    @pytest.mark.asyncio
    async def test_suggest_policy_finance(self, recommendation_service):
        """Test policy suggestion for finance text."""
        text = "Credit card payment for $500, account #123456789"

        with respx.mock:
            # Mock LLM response for finance text
            respx.post("http://ollama:11434/api/generate").mock(
                return_value=Response(
                    200,
                    json={
                        "response": json.dumps({
                            "recommended_context": "finance",
                            "confidence": 0.92,
                            "reasoning": "Contains financial PII (credit card, account number). PCI-DSS compliance required.",
                            "detected_domains": ["finance"],
                            "alternative_contexts": [],
                            "risk_warning": None
                        })
                    }
                )
            )

            result = await recommendation_service.suggest_policy(text)

            assert result["recommended_context"] == "finance"
            assert result["confidence"] >= 0.9
            assert "finance" in result["detected_domains"]
            assert "credit card" in result["reasoning"].lower() or "pci" in result["reasoning"].lower()

    @pytest.mark.asyncio
    async def test_suggest_policy_general(self, recommendation_service):
        """Test policy suggestion for general text."""
        text = "Please contact Sarah at sarah@example.com for more info"

        with respx.mock:
            # Mock LLM response for general text
            respx.post("http://ollama:11434/api/generate").mock(
                return_value=Response(
                    200,
                    json={
                        "response": json.dumps({
                            "recommended_context": "general",
                            "confidence": 0.85,
                            "reasoning": "Generic communication with basic PII (name, email). No specific compliance domain detected.",
                            "detected_domains": ["general"],
                            "alternative_contexts": [],
                            "risk_warning": None
                        })
                    }
                )
            )

            result = await recommendation_service.suggest_policy(text)

            assert result["recommended_context"] == "general"
            assert result["confidence"] > 0.7
            assert "general" in result["detected_domains"]

    @pytest.mark.asyncio
    async def test_suggest_policy_multi_domain(self, recommendation_service):
        """Test policy suggestion for text with multiple domains."""
        text = "Patient billing: credit card ending in 1234 for medical services"

        with respx.mock:
            # Mock LLM response for multi-domain text
            respx.post("http://ollama:11434/api/generate").mock(
                return_value=Response(
                    200,
                    json={
                        "response": json.dumps({
                            "recommended_context": "finance",
                            "confidence": 0.88,
                            "reasoning": "Mixed healthcare and finance data. Finance policy recommended as it has stricter thresholds.",
                            "detected_domains": ["healthcare", "finance"],
                            "alternative_contexts": ["healthcare"],
                            "risk_warning": "Text contains cross-domain PII - consider using strictest policy"
                        })
                    }
                )
            )

            result = await recommendation_service.suggest_policy(text)

            assert result["recommended_context"] == "finance"
            assert len(result["detected_domains"]) >= 2
            assert "healthcare" in result["detected_domains"]
            assert "finance" in result["detected_domains"]
            assert result["risk_warning"] is not None
            assert "cross-domain" in result["risk_warning"].lower()

    @pytest.mark.asyncio
    async def test_suggest_policy_with_markdown_wrapped_json(self, recommendation_service):
        """Test handling of markdown-wrapped JSON response."""
        text = "Patient data"

        with respx.mock:
            # Mock response with markdown wrapper
            respx.post("http://ollama:11434/api/generate").mock(
                return_value=Response(
                    200,
                    json={
                        "response": '```json\n{"recommended_context": "healthcare", "confidence": 0.9, "reasoning": "Patient data", "detected_domains": ["healthcare"], "alternative_contexts": [], "risk_warning": null}\n```'
                    }
                )
            )

            result = await recommendation_service.suggest_policy(text)

            assert result["recommended_context"] == "healthcare"
            assert result["confidence"] == 0.9

    @pytest.mark.asyncio
    async def test_suggest_policy_timeout_fallback(self, recommendation_service):
        """Test fallback to keyword-based recommendation on timeout."""
        text = "Patient John Doe needs medical treatment"

        with respx.mock:
            # Mock timeout
            respx.post("http://ollama:11434/api/generate").mock(
                side_effect=Exception("Connection timeout")
            )

            result = await recommendation_service.suggest_policy(text)

            # Should fallback to keyword-based detection
            assert result["recommended_context"] in ["healthcare", "general"]
            assert 0.0 <= result["confidence"] <= 1.0
            assert "fallback" in result["reasoning"].lower() or "unavailable" in result["reasoning"].lower()

    @pytest.mark.asyncio
    async def test_suggest_policy_malformed_json_fallback(self, recommendation_service):
        """Test fallback on malformed JSON response."""
        text = "Credit card transaction"

        with respx.mock:
            # Mock malformed JSON response
            respx.post("http://ollama:11434/api/generate").mock(
                return_value=Response(
                    200,
                    json={"response": "This is not valid JSON"}
                )
            )

            result = await recommendation_service.suggest_policy(text)

            # Should fallback to keyword-based detection
            assert result["recommended_context"] in ["finance", "general"]
            assert "detected_domains" in result

    @pytest.mark.asyncio
    async def test_suggest_policy_invalid_context_fallback(self, recommendation_service):
        """Test fallback when LLM returns invalid context."""
        text = "Some text"

        with respx.mock:
            # Mock response with invalid context
            respx.post("http://ollama:11434/api/generate").mock(
                return_value=Response(
                    200,
                    json={
                        "response": json.dumps({
                            "recommended_context": "invalid_context",
                            "confidence": 0.9,
                            "reasoning": "Test",
                            "detected_domains": ["invalid"]
                        })
                    }
                )
            )

            result = await recommendation_service.suggest_policy(text)

            # Should fallback to default recommendation
            assert result["recommended_context"] in ["general", "healthcare", "finance"]

    @pytest.mark.asyncio
    async def test_keyword_fallback_healthcare(self, recommendation_service):
        """Test keyword-based fallback correctly identifies healthcare text."""
        text = "Patient doctor hospital medical diagnosis treatment"

        with respx.mock:
            # Simulate LLM failure
            respx.post("http://ollama:11434/api/generate").mock(
                return_value=Response(500, json={"error": "Server error"})
            )

            result = await recommendation_service.suggest_policy(text)

            # Keyword fallback should detect healthcare
            assert result["recommended_context"] == "healthcare"
            assert "healthcare" in result["detected_domains"]

    @pytest.mark.asyncio
    async def test_keyword_fallback_finance(self, recommendation_service):
        """Test keyword-based fallback correctly identifies finance text."""
        text = "Credit card payment transaction account bank financial"

        with respx.mock:
            # Simulate LLM failure
            respx.post("http://ollama:11434/api/generate").mock(
                return_value=Response(500, json={"error": "Server error"})
            )

            result = await recommendation_service.suggest_policy(text)

            # Keyword fallback should detect finance
            assert result["recommended_context"] == "finance"
            assert "finance" in result["detected_domains"]

    @pytest.mark.asyncio
    async def test_keyword_fallback_general(self, recommendation_service):
        """Test keyword-based fallback defaults to general for ambiguous text."""
        text = "Hello world this is a test"

        with respx.mock:
            # Simulate LLM failure
            respx.post("http://ollama:11434/api/generate").mock(
                return_value=Response(500, json={"error": "Server error"})
            )

            result = await recommendation_service.suggest_policy(text)

            # Should default to general
            assert result["recommended_context"] == "general"
            assert "general" in result["detected_domains"]

    @pytest.mark.asyncio
    async def test_confidence_in_valid_range(self, recommendation_service):
        """Test that confidence is always between 0.0 and 1.0."""
        text = "Test text"

        with respx.mock:
            # Mock response with valid confidence
            respx.post("http://ollama:11434/api/generate").mock(
                return_value=Response(
                    200,
                    json={
                        "response": json.dumps({
                            "recommended_context": "general",
                            "confidence": 0.75,
                            "reasoning": "Test",
                            "detected_domains": ["general"],
                            "alternative_contexts": [],
                            "risk_warning": None
                        })
                    }
                )
            )

            result = await recommendation_service.suggest_policy(text)

            assert 0.0 <= result["confidence"] <= 1.0

    @pytest.mark.asyncio
    async def test_empty_text_handling(self, recommendation_service):
        """Test handling of empty text."""
        text = ""

        with respx.mock:
            respx.post("http://ollama:11434/api/generate").mock(
                return_value=Response(
                    200,
                    json={
                        "response": json.dumps({
                            "recommended_context": "general",
                            "confidence": 0.5,
                            "reasoning": "Empty text, using default policy",
                            "detected_domains": ["general"],
                            "alternative_contexts": [],
                            "risk_warning": None
                        })
                    }
                )
            )

            result = await recommendation_service.suggest_policy(text)

            assert result["recommended_context"] == "general"
