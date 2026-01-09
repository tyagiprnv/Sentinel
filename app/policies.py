"""
Policy Engine for context-aware PII redaction.

Supports different policy contexts (healthcare, finance, general) with
customizable entity filtering and restoration controls.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict
from presidio_analyzer import RecognizerResult


@dataclass
class RedactionPolicy:
    """
    Redaction policy configuration.

    Defines which PII entities to redact and restoration behavior
    for a specific context.
    """
    context: str
    enabled_entities: List[str] = field(default_factory=list)
    disabled_entities: List[str] = field(default_factory=list)
    restoration_allowed: bool = True
    min_confidence_threshold: float = 0.0
    description: str = ""

    def is_entity_allowed(self, entity_type: str) -> bool:
        """
        Check if an entity type should be redacted.

        Args:
            entity_type: Entity type (e.g., "PERSON", "EMAIL")

        Returns:
            True if entity should be redacted, False otherwise
        """
        # Disabled takes precedence over enabled
        if entity_type in self.disabled_entities:
            return False

        # If enabled_entities is empty, allow all
        if not self.enabled_entities:
            return True

        return entity_type in self.enabled_entities

    def meets_confidence_threshold(self, score: float) -> bool:
        """
        Check if confidence score meets minimum threshold.

        Args:
            score: Confidence score (0.0 to 1.0)

        Returns:
            True if score meets threshold
        """
        return score >= self.min_confidence_threshold


# Predefined policy contexts

GENERAL_POLICY = RedactionPolicy(
    context="general",
    enabled_entities=[
        "PERSON",
        "EMAIL_ADDRESS",
        "PHONE_NUMBER",
        "CREDIT_CARD",
        "US_SSN",
        "US_DRIVER_LICENSE",
        "US_PASSPORT",
        "IBAN_CODE",
        "IP_ADDRESS",
        "DATE_TIME",
        "LOCATION",
        "URL",
        "US_BANK_NUMBER"
    ],
    disabled_entities=[],
    restoration_allowed=True,
    min_confidence_threshold=0.0,
    description="General purpose policy - redacts all PII types with restoration allowed"
)

HEALTHCARE_POLICY = RedactionPolicy(
    context="healthcare",
    enabled_entities=[
        "PERSON",
        "PHONE_NUMBER",
        "EMAIL_ADDRESS",
        "US_SSN",
        "DATE_TIME",
        "LOCATION",
        "IP_ADDRESS"
    ],
    disabled_entities=[],
    restoration_allowed=False,
    min_confidence_threshold=0.5,
    description="Healthcare policy (HIPAA-compliant) - redacts PHI with no restoration"
)

FINANCE_POLICY = RedactionPolicy(
    context="finance",
    enabled_entities=[
        "PERSON",
        "US_SSN",
        "CREDIT_CARD",
        "IBAN_CODE",
        "PHONE_NUMBER",
        "EMAIL_ADDRESS",
        "US_BANK_NUMBER",
        "US_DRIVER_LICENSE"
    ],
    disabled_entities=[],
    restoration_allowed=False,
    min_confidence_threshold=0.6,
    description="Finance policy (PCI-DSS) - redacts financial PII with no restoration"
)


class PolicyEngine:
    """
    Policy engine for context-aware PII redaction.

    Manages policy loading, merging, and entity filtering.
    """

    def __init__(self):
        """Initialize policy engine with predefined policies."""
        self.policies: Dict[str, RedactionPolicy] = {
            "general": GENERAL_POLICY,
            "healthcare": HEALTHCARE_POLICY,
            "finance": FINANCE_POLICY
        }

    def load_policy(self, context: str) -> RedactionPolicy:
        """
        Load policy by context name.

        Args:
            context: Policy context ("general", "healthcare", "finance")

        Returns:
            RedactionPolicy for the context

        Raises:
            ValueError: If context not found
        """
        if context not in self.policies:
            raise ValueError(
                f"Unknown policy context: {context}. "
                f"Available: {list(self.policies.keys())}"
            )
        return self.policies[context]

    def merge_policies(
        self,
        global_policy: RedactionPolicy,
        request_policy: Optional[Dict] = None
    ) -> RedactionPolicy:
        """
        Merge request-level policy overrides with global policy.

        Request policies can override specific fields. Missing fields
        inherit from global policy.

        Args:
            global_policy: Base policy from configuration
            request_policy: Optional request-level overrides

        Returns:
            Merged RedactionPolicy
        """
        if not request_policy:
            return global_policy

        # Start with global policy as base
        merged = RedactionPolicy(
            context=request_policy.get("context", global_policy.context),
            enabled_entities=request_policy.get("enabled_entities", global_policy.enabled_entities),
            disabled_entities=request_policy.get("disabled_entities", global_policy.disabled_entities),
            restoration_allowed=request_policy.get("restoration_allowed", global_policy.restoration_allowed),
            min_confidence_threshold=request_policy.get("min_confidence_threshold", global_policy.min_confidence_threshold),
            description=request_policy.get("description", global_policy.description)
        )

        return merged

    def filter_entities(
        self,
        analyzer_results: List[RecognizerResult],
        policy: RedactionPolicy
    ) -> List[RecognizerResult]:
        """
        Filter entity results based on policy.

        Removes entities that:
        - Are not allowed by the policy
        - Don't meet minimum confidence threshold

        Args:
            analyzer_results: Results from Presidio analyzer
            policy: Redaction policy to apply

        Returns:
            Filtered list of RecognizerResult
        """
        filtered = []

        for result in analyzer_results:
            # Check if entity type is allowed
            if not policy.is_entity_allowed(result.entity_type):
                continue

            # Check confidence threshold
            if not policy.meets_confidence_threshold(result.score):
                continue

            filtered.append(result)

        return filtered

    def register_policy(self, policy: RedactionPolicy):
        """
        Register a custom policy.

        Args:
            policy: Custom RedactionPolicy to register
        """
        self.policies[policy.context] = policy

    def get_available_contexts(self) -> List[str]:
        """
        Get list of available policy contexts.

        Returns:
            List of context names
        """
        return list(self.policies.keys())
