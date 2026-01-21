import redis
import uuid
from typing import Optional
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig
from app.policies import PolicyEngine, RedactionPolicy
from app.config import get_settings

class RedactorService:
    # Issue 5 fix: Class-level singleton instances to prevent reloading 500MB model
    _analyzer_instance = None
    _anonymizer_instance = None

    def __init__(self, policy_engine: Optional[PolicyEngine] = None):
        # Use lazy-loaded singleton instances
        self.analyzer = self._get_analyzer()
        self.anonymizer = self._get_anonymizer()

        # Issue 3 fix: Use config settings instead of hardcoded values
        settings = get_settings()
        self.db = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            password=settings.redis_password,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True
        )

        self.policy_engine = policy_engine or PolicyEngine()

    @classmethod
    def _get_analyzer(cls):
        """Lazy-load AnalyzerEngine as singleton (500MB model)."""
        if cls._analyzer_instance is None:
            print("Initializing Presidio AnalyzerEngine (one-time load)...")
            cls._analyzer_instance = AnalyzerEngine()
            print("AnalyzerEngine ready")
        return cls._analyzer_instance

    @classmethod
    def _get_anonymizer(cls):
        """Lazy-load AnonymizerEngine as singleton."""
        if cls._anonymizer_instance is None:
            cls._anonymizer_instance = AnonymizerEngine()
        return cls._anonymizer_instance

    def redact_and_store(self, text: str, policy: Optional[RedactionPolicy] = None):
        results = self.analyzer.analyze(text=text, language='en')

        # Apply policy filtering if policy is provided
        if policy:
            results = self.policy_engine.filter_entities(results, policy)
        
        # This list will track ONLY the keys created in THIS specific function call
        created_keys = []
        
        def store_in_redis(pii_text):
            token_id = uuid.uuid4().hex[:16]  # Issue 1 fix: 16 chars prevents collisions
            token = f"[REDACTED_{token_id}]"

            # Store PII mapping with policy metadata
            # Store restoration permission alongside the PII value
            value_with_metadata = pii_text
            if policy:
                # Store metadata in separate key for restoration validation
                meta_key = f"{token}:policy"
                meta_value = f"{policy.context}:{policy.restoration_allowed}"
                self.db.set(meta_key, meta_value, ex=86400)

            # Save mapping and track the key
            self.db.set(token, value_with_metadata, ex=86400)
            created_keys.append(token)
            return token

        anonymized_result = self.anonymizer.anonymize(
            text=text,
            analyzer_results=results,
            operators={"DEFAULT": OperatorConfig("custom", {"lambda": store_in_redis})}
        )
        
        scores = [res.score for res in results]
        
        # Return the keys alongside the text and scores
        return anonymized_result.text, scores, created_keys

    def restore(self, redacted_text: str, check_policy: bool = True) -> dict:
        """
        Restore redacted text from Redis tokens.

        Issue 4 fix: Returns dict with warnings for missing tokens
        Issue 7 fix: Case-insensitive boolean comparison

        Args:
            redacted_text: Text with [REDACTED_xxxx] tokens
            check_policy: If True, check policy metadata before restoration

        Returns:
            dict with:
            - restored_text: Text with PII restored
            - tokens_found: Number successfully restored
            - tokens_missing: List of missing token IDs
            - warnings: Warning messages
        """
        import re
        tokens = re.findall(r"\[REDACTED_[a-z0-9]+\]", redacted_text)
        restored_text = redacted_text

        tokens_found = 0
        tokens_missing = []
        warnings = []

        for token in tokens:
            # Check policy metadata if requested
            if check_policy:
                meta_key = f"{token}:policy"
                meta_value = self.db.get(meta_key)
                if meta_value:
                    # Parse metadata: "context:restoration_allowed"
                    parts = meta_value.split(":")
                    if len(parts) >= 2:
                        # Issue 7 fix: case-insensitive comparison
                        restoration_allowed = parts[1].lower() == "true"
                        if not restoration_allowed:
                            # Policy blocks restoration
                            raise PermissionError(
                                f"Restoration not allowed for policy context: {parts[0]}"
                            )

            # Attempt restoration
            original_value = self.db.get(token)
            if original_value:
                restored_text = restored_text.replace(token, original_value)
                tokens_found += 1
            else:
                tokens_missing.append(token)
                warnings.append(f"Token {token} expired or not found in Redis")

        return {
            "restored_text": restored_text,
            "tokens_found": tokens_found,
            "tokens_missing": tokens_missing,
            "warnings": warnings
        }

redactor = RedactorService()