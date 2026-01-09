import redis
import uuid
from typing import Optional
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig
from app.policies import PolicyEngine, RedactionPolicy

class RedactorService:
    def __init__(self, policy_engine: Optional[PolicyEngine] = None):
        self.analyzer = AnalyzerEngine()
        self.anonymizer = AnonymizerEngine()
        self.db = redis.Redis(host='redis', port=6379, decode_responses=True)
        self.policy_engine = policy_engine or PolicyEngine()

    def redact_and_store(self, text: str, policy: Optional[RedactionPolicy] = None):
        results = self.analyzer.analyze(text=text, language='en')

        # Apply policy filtering if policy is provided
        if policy:
            results = self.policy_engine.filter_entities(results, policy)
        
        # This list will track ONLY the keys created in THIS specific function call
        created_keys = []
        
        def store_in_redis(pii_text):
            token_id = uuid.uuid4().hex[:4]
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

    def restore(self, redacted_text: str, check_policy: bool = True):
        """
        Restore redacted text from Redis tokens.

        Args:
            redacted_text: Text with [REDACTED_xxxx] tokens
            check_policy: If True, check policy metadata before restoration

        Returns:
            Restored text (or raises exception if restoration blocked by policy)
        """
        import re
        tokens = re.findall(r"\[REDACTED_[a-z0-9]+\]", redacted_text)
        restored_text = redacted_text

        for token in tokens:
            # Check policy metadata if requested
            if check_policy:
                meta_key = f"{token}:policy"
                meta_value = self.db.get(meta_key)
                if meta_value:
                    # Parse metadata: "context:restoration_allowed"
                    parts = meta_value.split(":")
                    if len(parts) >= 2:
                        restoration_allowed = parts[1] == "True"
                        if not restoration_allowed:
                            # Policy blocks restoration
                            raise PermissionError(
                                f"Restoration not allowed for policy context: {parts[0]}"
                            )

            original_value = self.db.get(token)
            if original_value:
                restored_text = restored_text.replace(token, original_value)
        return restored_text

redactor = RedactorService()