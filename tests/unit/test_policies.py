"""
Unit tests for Policy Engine.

Tests policy loading, merging, entity filtering, and confidence thresholds.
"""

import pytest
from presidio_analyzer import RecognizerResult, EntityRecognizer
from app.policies import (
    PolicyEngine,
    RedactionPolicy,
    GENERAL_POLICY,
    HEALTHCARE_POLICY,
    FINANCE_POLICY
)


class TestRedactionPolicy:
    """Tests for RedactionPolicy dataclass."""

    def test_policy_creation(self):
        """Test creating a custom policy."""
        policy = RedactionPolicy(
            context="test",
            enabled_entities=["EMAIL_ADDRESS", "PERSON"],
            disabled_entities=["PHONE_NUMBER"],
            restoration_allowed=True,
            min_confidence_threshold=0.7
        )

        assert policy.context == "test"
        assert "EMAIL_ADDRESS" in policy.enabled_entities
        assert "PHONE_NUMBER" in policy.disabled_entities
        assert policy.restoration_allowed is True
        assert policy.min_confidence_threshold == 0.7

    def test_is_entity_allowed_enabled(self):
        """Test entity is allowed when in enabled_entities."""
        policy = RedactionPolicy(
            context="test",
            enabled_entities=["EMAIL_ADDRESS", "PERSON"],
            disabled_entities=[]
        )

        assert policy.is_entity_allowed("EMAIL_ADDRESS") is True
        assert policy.is_entity_allowed("PERSON") is True
        assert policy.is_entity_allowed("PHONE_NUMBER") is False

    def test_is_entity_allowed_disabled_takes_precedence(self):
        """Test that disabled_entities takes precedence over enabled_entities."""
        policy = RedactionPolicy(
            context="test",
            enabled_entities=["EMAIL_ADDRESS", "PERSON", "PHONE_NUMBER"],
            disabled_entities=["PHONE_NUMBER"]  # Explicitly disabled
        )

        assert policy.is_entity_allowed("EMAIL_ADDRESS") is True
        assert policy.is_entity_allowed("PERSON") is True
        assert policy.is_entity_allowed("PHONE_NUMBER") is False  # Disabled takes precedence

    def test_is_entity_allowed_empty_enabled_allows_all(self):
        """Test that empty enabled_entities allows all entities."""
        policy = RedactionPolicy(
            context="test",
            enabled_entities=[],  # Empty = allow all
            disabled_entities=[]
        )

        assert policy.is_entity_allowed("EMAIL_ADDRESS") is True
        assert policy.is_entity_allowed("PERSON") is True
        assert policy.is_entity_allowed("ANYTHING") is True

    def test_is_entity_allowed_empty_enabled_with_disabled(self):
        """Test empty enabled with specific disabled entities."""
        policy = RedactionPolicy(
            context="test",
            enabled_entities=[],  # Allow all
            disabled_entities=["PHONE_NUMBER"]  # Except this
        )

        assert policy.is_entity_allowed("EMAIL_ADDRESS") is True
        assert policy.is_entity_allowed("PERSON") is True
        assert policy.is_entity_allowed("PHONE_NUMBER") is False

    def test_meets_confidence_threshold(self):
        """Test confidence threshold checking."""
        policy = RedactionPolicy(
            context="test",
            min_confidence_threshold=0.7
        )

        assert policy.meets_confidence_threshold(0.8) is True
        assert policy.meets_confidence_threshold(0.7) is True  # Equal is allowed
        assert policy.meets_confidence_threshold(0.6) is False
        assert policy.meets_confidence_threshold(0.0) is False


class TestPolicyEngine:
    """Tests for PolicyEngine class."""

    def test_load_policy_general(self):
        """Test loading general policy."""
        engine = PolicyEngine()
        policy = engine.load_policy("general")

        assert policy.context == "general"
        assert policy.restoration_allowed is False  # Default is opt-in (False)
        assert len(policy.enabled_entities) > 0

    def test_load_policy_healthcare(self):
        """Test loading healthcare policy."""
        engine = PolicyEngine()
        policy = engine.load_policy("healthcare")

        assert policy.context == "healthcare"
        assert policy.restoration_allowed is False
        assert "PERSON" in policy.enabled_entities
        assert "EMAIL_ADDRESS" in policy.enabled_entities

    def test_load_policy_finance(self):
        """Test loading finance policy."""
        engine = PolicyEngine()
        policy = engine.load_policy("finance")

        assert policy.context == "finance"
        assert policy.restoration_allowed is False
        assert "CREDIT_CARD" in policy.enabled_entities
        assert "US_SSN" in policy.enabled_entities

    def test_load_policy_invalid_context(self):
        """Test loading policy with invalid context raises ValueError."""
        engine = PolicyEngine()

        with pytest.raises(ValueError, match="Unknown policy context"):
            engine.load_policy("invalid_context")

    def test_merge_policies_no_override(self):
        """Test merging with no override returns global policy."""
        engine = PolicyEngine()
        global_policy = GENERAL_POLICY

        merged = engine.merge_policies(global_policy, None)

        assert merged.context == global_policy.context
        assert merged.enabled_entities == global_policy.enabled_entities

    def test_merge_policies_context_override(self):
        """Test merging with context override."""
        engine = PolicyEngine()
        global_policy = GENERAL_POLICY
        request_policy = {"context": "custom_context"}

        merged = engine.merge_policies(global_policy, request_policy)

        assert merged.context == "custom_context"
        assert merged.enabled_entities == global_policy.enabled_entities  # Inherited

    def test_merge_policies_enabled_entities_override(self):
        """Test merging with enabled_entities override."""
        engine = PolicyEngine()
        global_policy = GENERAL_POLICY
        request_policy = {
            "enabled_entities": ["EMAIL_ADDRESS", "PERSON"]
        }

        merged = engine.merge_policies(global_policy, request_policy)

        assert merged.enabled_entities == ["EMAIL_ADDRESS", "PERSON"]
        assert merged.context == global_policy.context  # Inherited

    def test_merge_policies_restoration_override(self):
        """Test merging with restoration_allowed override."""
        engine = PolicyEngine()
        global_policy = HEALTHCARE_POLICY  # restoration_allowed = False
        request_policy = {
            "restoration_allowed": True  # Override to allow restoration
        }

        merged = engine.merge_policies(global_policy, request_policy)

        assert merged.restoration_allowed is True
        assert merged.context == global_policy.context

    def test_merge_policies_full_override(self):
        """Test merging with all fields overridden."""
        engine = PolicyEngine()
        global_policy = GENERAL_POLICY
        request_policy = {
            "context": "custom",
            "enabled_entities": ["EMAIL_ADDRESS"],
            "disabled_entities": ["PHONE_NUMBER"],
            "restoration_allowed": False,
            "min_confidence_threshold": 0.9
        }

        merged = engine.merge_policies(global_policy, request_policy)

        assert merged.context == "custom"
        assert merged.enabled_entities == ["EMAIL_ADDRESS"]
        assert merged.disabled_entities == ["PHONE_NUMBER"]
        assert merged.restoration_allowed is False
        assert merged.min_confidence_threshold == 0.9

    def test_filter_entities_no_filtering(self):
        """Test filtering with policy that allows all entities."""
        engine = PolicyEngine()
        policy = RedactionPolicy(
            context="test",
            enabled_entities=[],  # Allow all
            disabled_entities=[],
            min_confidence_threshold=0.0
        )

        # Mock analyzer results
        results = [
            RecognizerResult(entity_type="EMAIL_ADDRESS", start=0, end=10, score=0.9),
            RecognizerResult(entity_type="PERSON", start=11, end=20, score=0.8),
            RecognizerResult(entity_type="PHONE_NUMBER", start=21, end=30, score=0.7),
        ]

        filtered = engine.filter_entities(results, policy)

        assert len(filtered) == 3  # All entities allowed

    def test_filter_entities_by_type(self):
        """Test filtering entities by type."""
        engine = PolicyEngine()
        policy = RedactionPolicy(
            context="test",
            enabled_entities=["EMAIL_ADDRESS", "PERSON"],  # Only these
            disabled_entities=[],
            min_confidence_threshold=0.0
        )

        results = [
            RecognizerResult(entity_type="EMAIL_ADDRESS", start=0, end=10, score=0.9),
            RecognizerResult(entity_type="PERSON", start=11, end=20, score=0.8),
            RecognizerResult(entity_type="PHONE_NUMBER", start=21, end=30, score=0.7),
        ]

        filtered = engine.filter_entities(results, policy)

        assert len(filtered) == 2
        assert filtered[0].entity_type == "EMAIL_ADDRESS"
        assert filtered[1].entity_type == "PERSON"

    def test_filter_entities_by_confidence(self):
        """Test filtering entities by confidence threshold."""
        engine = PolicyEngine()
        policy = RedactionPolicy(
            context="test",
            enabled_entities=[],  # Allow all types
            disabled_entities=[],
            min_confidence_threshold=0.75  # Only high confidence
        )

        results = [
            RecognizerResult(entity_type="EMAIL_ADDRESS", start=0, end=10, score=0.9),  # Pass
            RecognizerResult(entity_type="PERSON", start=11, end=20, score=0.8),  # Pass
            RecognizerResult(entity_type="PHONE_NUMBER", start=21, end=30, score=0.7),  # Fail
            RecognizerResult(entity_type="LOCATION", start=31, end=40, score=0.5),  # Fail
        ]

        filtered = engine.filter_entities(results, policy)

        assert len(filtered) == 2
        assert all(result.score >= 0.75 for result in filtered)

    def test_filter_entities_combined_rules(self):
        """Test filtering with both type and confidence rules."""
        engine = PolicyEngine()
        policy = RedactionPolicy(
            context="test",
            enabled_entities=["EMAIL_ADDRESS", "PERSON", "PHONE_NUMBER"],
            disabled_entities=["PERSON"],  # Explicitly disabled
            min_confidence_threshold=0.7
        )

        results = [
            RecognizerResult(entity_type="EMAIL_ADDRESS", start=0, end=10, score=0.9),  # Pass
            RecognizerResult(entity_type="PERSON", start=11, end=20, score=0.9),  # Fail (disabled)
            RecognizerResult(entity_type="PHONE_NUMBER", start=21, end=30, score=0.8),  # Pass
            RecognizerResult(entity_type="PHONE_NUMBER", start=31, end=40, score=0.6),  # Fail (confidence)
        ]

        filtered = engine.filter_entities(results, policy)

        assert len(filtered) == 2
        assert filtered[0].entity_type == "EMAIL_ADDRESS"
        assert filtered[1].entity_type == "PHONE_NUMBER"
        assert filtered[1].score == 0.8

    def test_register_custom_policy(self):
        """Test registering a custom policy."""
        engine = PolicyEngine()
        custom_policy = RedactionPolicy(
            context="custom",
            enabled_entities=["EMAIL_ADDRESS"],
            restoration_allowed=True
        )

        engine.register_policy(custom_policy)

        loaded = engine.load_policy("custom")
        assert loaded.context == "custom"
        assert loaded.enabled_entities == ["EMAIL_ADDRESS"]

    def test_get_available_contexts(self):
        """Test getting list of available policy contexts."""
        engine = PolicyEngine()

        contexts = engine.get_available_contexts()

        assert "general" in contexts
        assert "healthcare" in contexts
        assert "finance" in contexts
        assert len(contexts) >= 3


class TestPredefinedPolicies:
    """Tests for predefined policy configurations."""

    def test_general_policy_configuration(self):
        """Test general policy has expected configuration."""
        assert GENERAL_POLICY.context == "general"
        assert GENERAL_POLICY.restoration_allowed is False  # Opt-in by default
        assert GENERAL_POLICY.min_confidence_threshold == 0.0
        assert len(GENERAL_POLICY.enabled_entities) > 0

    def test_healthcare_policy_configuration(self):
        """Test healthcare policy has HIPAA-compliant configuration."""
        assert HEALTHCARE_POLICY.context == "healthcare"
        assert HEALTHCARE_POLICY.restoration_allowed is False  # HIPAA compliance
        assert HEALTHCARE_POLICY.min_confidence_threshold >= 0.5
        assert "PERSON" in HEALTHCARE_POLICY.enabled_entities
        assert "US_SSN" in HEALTHCARE_POLICY.enabled_entities

    def test_finance_policy_configuration(self):
        """Test finance policy has PCI-DSS configuration."""
        assert FINANCE_POLICY.context == "finance"
        assert FINANCE_POLICY.restoration_allowed is False  # PCI-DSS compliance
        assert FINANCE_POLICY.min_confidence_threshold >= 0.6
        assert "CREDIT_CARD" in FINANCE_POLICY.enabled_entities
        assert "US_SSN" in FINANCE_POLICY.enabled_entities
