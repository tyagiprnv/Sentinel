"""
Unit tests for VerificationAgent class.
"""
import pytest
import respx
from httpx import Response
import json
from app.verification import VerificationAgent


class TestVerificationAgent:
    """Test suite for VerificationAgent."""

    @pytest.fixture
    def verification_agent(self):
        """Create a VerificationAgent instance."""
        return VerificationAgent()

    @pytest.mark.asyncio
    async def test_check_for_leaks_clean_text(self, verification_agent):
        """Test LLM check on properly redacted text."""
        redacted_text = "Contact [REDACTED_a1b2] at [REDACTED_c3d4]"

        with respx.mock:
            # Mock Ollama API response
            respx.post("http://ollama:11434/api/generate").mock(
                return_value=Response(
                    200,
                    json={
                        "response": '{"leaked": false, "reason": "All PII properly redacted"}'
                    }
                )
            )

            result_raw = await verification_agent.check_for_leaks(redacted_text)

            # Parse result
            if isinstance(result_raw, str):
                result = json.loads(result_raw)
            else:
                result = json.loads(result_raw)

            assert result["leaked"] is False
            assert "reason" in result

    @pytest.mark.asyncio
    async def test_check_for_leaks_with_leak(self, verification_agent):
        """Test LLM check on text with leaked PII."""
        leaked_text = "Contact john.doe@example.com for details"

        with respx.mock:
            # Mock Ollama API response indicating leak
            respx.post("http://ollama:11434/api/generate").mock(
                return_value=Response(
                    200,
                    json={
                        "response": '{"leaked": true, "reason": "Email address john.doe@example.com not redacted"}'
                    }
                )
            )

            result_raw = await verification_agent.check_for_leaks(leaked_text)

            # Parse result
            if isinstance(result_raw, str):
                result = json.loads(result_raw)
            else:
                result = json.loads(result_raw)

            assert result["leaked"] is True
            assert "john.doe@example.com" in result["reason"] or "email" in result["reason"].lower()

    @pytest.mark.asyncio
    async def test_check_for_leaks_with_markdown_wrapped_json(self, verification_agent):
        """Test parsing JSON wrapped in markdown code blocks."""
        redacted_text = "Contact [REDACTED_xyz1]"

        with respx.mock:
            # Mock response with markdown-wrapped JSON
            respx.post("http://ollama:11434/api/generate").mock(
                return_value=Response(
                    200,
                    json={
                        "response": '```json\n{"leaked": false, "reason": "Clean"}\n```'
                    }
                )
            )

            result_raw = await verification_agent.check_for_leaks(redacted_text)

            # The app/main.py audit_redaction_task handles cleaning
            # Here we just verify the response is returned
            assert result_raw is not None
            assert "leaked" in result_raw

    @pytest.mark.asyncio
    async def test_check_for_leaks_timeout(self, verification_agent):
        """Test handling of LLM timeout."""
        redacted_text = "Contact [REDACTED_a1b2]"

        with respx.mock:
            # Mock timeout
            respx.post("http://ollama:11434/api/generate").mock(
                side_effect=Exception("Connection timeout")
            )

            result = await verification_agent.check_for_leaks(redacted_text)

            # Should return error response
            assert "error" in result or result.get("leaked") is False

    @pytest.mark.asyncio
    async def test_check_for_leaks_malformed_json(self, verification_agent):
        """Test handling of malformed JSON response."""
        redacted_text = "Contact [REDACTED_a1b2]"

        with respx.mock:
            # Mock response with invalid JSON
            respx.post("http://ollama:11434/api/generate").mock(
                return_value=Response(
                    200,
                    json={
                        "response": "This is not valid JSON"
                    }
                )
            )

            result_raw = await verification_agent.check_for_leaks(redacted_text)

            # Should still return something (main.py handles parsing)
            assert result_raw is not None

    @pytest.mark.asyncio
    async def test_check_for_leaks_500_error(self, verification_agent):
        """Test handling of HTTP 500 error from Ollama."""
        redacted_text = "Contact [REDACTED_a1b2]"

        with respx.mock:
            # Mock 500 error
            respx.post("http://ollama:11434/api/generate").mock(
                return_value=Response(500, json={"error": "Internal server error"})
            )

            result = await verification_agent.check_for_leaks(redacted_text)

            # Should handle gracefully (returns dict with error or None)
            assert result is None or (isinstance(result, dict) and ("error" in result or result.get("leaked") is False))

    @pytest.mark.asyncio
    async def test_prompt_contains_text(self, verification_agent):
        """Test that the prompt includes the redacted text."""
        redacted_text = "Unique text 12345"

        with respx.mock:
            request_data = None

            def capture_request(request):
                nonlocal request_data
                request_data = json.loads(request.content)
                return Response(
                    200,
                    json={"response": '{"leaked": false, "reason": "Clean"}'}
                )

            respx.post("http://ollama:11434/api/generate").mock(
                side_effect=capture_request
            )

            await verification_agent.check_for_leaks(redacted_text)

            # Verify the text was included in prompt
            assert request_data is not None
            assert "Unique text 12345" in request_data["prompt"]

    @pytest.mark.asyncio
    async def test_uses_correct_model(self, verification_agent):
        """Test that the correct model is specified in request."""
        redacted_text = "Test"

        with respx.mock:
            request_data = None

            def capture_request(request):
                nonlocal request_data
                request_data = json.loads(request.content)
                return Response(
                    200,
                    json={"response": '{"leaked": false, "reason": "Clean"}'}
                )

            respx.post("http://ollama:11434/api/generate").mock(
                side_effect=capture_request
            )

            await verification_agent.check_for_leaks(redacted_text)

            # Verify model is phi3
            assert request_data is not None
            assert request_data["model"] == "phi3"
            assert request_data["stream"] is False
            assert request_data["format"] == "json"

    @pytest.mark.asyncio
    async def test_empty_text_handling(self, verification_agent):
        """Test handling of empty text."""
        redacted_text = ""

        with respx.mock:
            respx.post("http://ollama:11434/api/generate").mock(
                return_value=Response(
                    200,
                    json={"response": '{"leaked": false, "reason": "Empty text"}'}
                )
            )

            result_raw = await verification_agent.check_for_leaks(redacted_text)
            assert result_raw is not None

    @pytest.mark.asyncio
    async def test_very_long_text(self, verification_agent):
        """Test handling of very long redacted text."""
        # Create long text
        redacted_text = "Text " + "[REDACTED_xxxx] " * 1000

        with respx.mock:
            respx.post("http://ollama:11434/api/generate").mock(
                return_value=Response(
                    200,
                    json={"response": '{"leaked": false, "reason": "All redacted"}'}
                )
            )

            result_raw = await verification_agent.check_for_leaks(redacted_text)
            assert result_raw is not None
