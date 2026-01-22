"""
LLM-based verification agent for detecting PII leaks in redacted text.

Uses advanced prompt engineering techniques (few-shot, chain-of-thought)
to improve leak detection accuracy.
"""
import httpx
from app.config import get_settings
from app.prompts.verification_prompts import get_prompt


class VerificationAgent:
    """
    LLM-powered agent for verifying PII redaction quality.

    Supports multiple prompt strategies configurable via settings.
    """

    def __init__(self):
        """Initialize with configuration from settings."""
        self.settings = get_settings()
        self.ollama_url = self.settings.ollama_url
        self.model = self.settings.ollama_model
        self.timeout = self.settings.ollama_timeout
        self.prompt_version = self.settings.prompt_version

    async def check_for_leaks(self, redacted_text: str, prompt_version: str = None, risk_mode: bool = False) -> dict:
        """
        Check redacted text for PII leaks using LLM.

        Args:
            redacted_text: Text that has been redacted
            prompt_version: Optional prompt version override (v1_basic, v2_cot, v3_few_shot)
            risk_mode: If True, return risk scores instead of boolean leaked status

        Returns:
            If risk_mode=False: Dictionary with 'leaked' (bool), 'reason' (str), and optional 'error'
            If risk_mode=True: Dictionary with 'risk_score' (float), 'risk_factors' (list),
                               'recommended_action' (str), 'confidence' (float)
        """
        # Use specified version or default from config
        version = prompt_version or self.prompt_version

        # Generate prompt using advanced prompting system
        prompt = get_prompt(
            version=version,
            text=redacted_text,
            risk_mode=risk_mode,
            num_examples=self.settings.few_shot_examples_count
        )

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
                    # Return the JSON response string (will be parsed by caller)
                    return response.json().get("response")
                else:
                    # Return safe default on error as JSON string for consistency
                    import json
                    return json.dumps({"leaked": False, "error": f"HTTP {response.status_code}"})

            except httpx.TimeoutException:
                import json
                return json.dumps({"leaked": False, "error": "Timeout waiting for LLM response"})
            except Exception as e:
                import json
                return json.dumps({"leaked": False, "error": str(e)})


# Global verifier instance
verifier = VerificationAgent()