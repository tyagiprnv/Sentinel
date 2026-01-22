"""
Policy recommendation service using LLM-based domain detection.

Analyzes text content to suggest the most appropriate policy context.
"""
import httpx
import json
from app.config import get_settings
from app.prompts.policy_prompts import get_policy_recommendation_prompt


class PolicyRecommendationService:
    """
    LLM-powered service for recommending policy contexts based on text analysis.
    """

    def __init__(self):
        """Initialize with configuration from settings."""
        self.settings = get_settings()
        self.ollama_url = self.settings.ollama_url
        self.model = self.settings.ollama_model
        self.timeout = self.settings.ollama_timeout

    async def suggest_policy(self, text: str) -> dict:
        """
        Analyze text and suggest the most appropriate policy context.

        Args:
            text: Input text to analyze

        Returns:
            Dictionary with:
            - recommended_context: str (general/healthcare/finance)
            - confidence: float (0.0-1.0)
            - reasoning: str
            - detected_domains: list[str]
            - alternative_contexts: list[str]
            - risk_warning: str | None
        """
        # Generate prompt
        prompt = get_policy_recommendation_prompt(text)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    self.ollama_url,
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "format": "json"
                    }
                )

                if response.status_code == 200:
                    result_str = response.json().get("response")

                    # Parse JSON response
                    try:
                        result = self._parse_json_response(result_str)

                        # Validate required fields
                        if not self._validate_response(result):
                            return self._get_default_recommendation(text)

                        return result

                    except json.JSONDecodeError as e:
                        # Fallback to default recommendation
                        return self._get_default_recommendation(text)

                else:
                    # Return default recommendation on error
                    return self._get_default_recommendation(text)

            except httpx.TimeoutException:
                return self._get_default_recommendation(text, error="LLM timeout")

            except Exception as e:
                return self._get_default_recommendation(text, error=str(e))

    def _parse_json_response(self, response_str: str) -> dict:
        """
        Parse LLM JSON response with markdown wrapper handling.

        Args:
            response_str: Raw response string from LLM

        Returns:
            Parsed dictionary

        Raises:
            json.JSONDecodeError: If JSON is invalid
        """
        # Clean markdown wrappers
        import re
        clean_json = response_str.strip()
        clean_json = re.sub(r'^```json\s*', '', clean_json)
        clean_json = re.sub(r'\s*```$', '', clean_json)
        clean_json = clean_json.strip()

        return json.loads(clean_json)

    def _validate_response(self, result: dict) -> bool:
        """
        Validate that response contains required fields.

        Args:
            result: Parsed response dictionary

        Returns:
            True if valid, False otherwise
        """
        required_fields = ["recommended_context", "confidence", "reasoning", "detected_domains"]

        # Check required fields exist
        if not all(field in result for field in required_fields):
            return False

        # Validate context is valid
        valid_contexts = ["general", "healthcare", "finance"]
        if result["recommended_context"] not in valid_contexts:
            return False

        # Validate confidence is in range
        try:
            confidence = float(result["confidence"])
            if not 0.0 <= confidence <= 1.0:
                return False
        except (ValueError, TypeError):
            return False

        return True

    def _get_default_recommendation(self, text: str, error: str = None) -> dict:
        """
        Return default policy recommendation (general context).

        Args:
            text: Original text
            error: Optional error message

        Returns:
            Default recommendation dictionary
        """
        # Simple keyword-based fallback
        text_lower = text.lower()

        # Healthcare keywords
        healthcare_keywords = ["patient", "doctor", "hospital", "medical", "diagnosis", "treatment", "phi", "hipaa"]
        # Finance keywords
        finance_keywords = ["credit card", "payment", "transaction", "account", "bank", "financial", "pci", "invoice"]

        healthcare_score = sum(1 for kw in healthcare_keywords if kw in text_lower)
        finance_score = sum(1 for kw in finance_keywords if kw in text_lower)

        if healthcare_score > finance_score and healthcare_score >= 2:
            context = "healthcare"
            confidence = min(0.7, 0.5 + (healthcare_score * 0.1))
            reasoning = f"Keyword-based fallback detected healthcare terms (LLM unavailable: {error})" if error else "Keyword-based fallback detected healthcare terms"
            domains = ["healthcare"]
        elif finance_score > healthcare_score and finance_score >= 2:
            context = "finance"
            confidence = min(0.7, 0.5 + (finance_score * 0.1))
            reasoning = f"Keyword-based fallback detected finance terms (LLM unavailable: {error})" if error else "Keyword-based fallback detected finance terms"
            domains = ["finance"]
        else:
            context = "general"
            confidence = 0.6
            reasoning = f"No clear domain detected, using default general policy (LLM unavailable: {error})" if error else "No clear domain detected, using default general policy"
            domains = ["general"]

        return {
            "recommended_context": context,
            "confidence": confidence,
            "reasoning": reasoning,
            "detected_domains": domains,
            "alternative_contexts": [],
            "risk_warning": None
        }


# Global service instance
policy_recommender = PolicyRecommendationService()
