from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import uuid
from app.policy_schemas import PolicyRequest, PolicyResponse

class RedactRequest(BaseModel):
    text: str = Field(..., example="My name is Jane Doe and my email is jane@example.com")
    policy: Optional[PolicyRequest] = Field(
        None,
        description="Optional policy override for this request",
        example={"context": "healthcare"}
    )

class RedactResponse(BaseModel):
    original_length: int
    redacted_text: str
    entities_found: list[str]
    policy_applied: Optional[PolicyResponse] = Field(
        None,
        description="Policy that was applied to this request"
    )


# Risk Scoring Schemas

class RiskAnalysis(BaseModel):
    """Risk analysis result from LLM auditor."""
    risk_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Risk score from 0.0 (no risk) to 1.0 (critical risk)"
    )
    risk_factors: List[str] = Field(
        ...,
        description="List of specific risk factors identified"
    )
    recommended_action: str = Field(
        ...,
        description="Recommended action: 'allow', 'alert', or 'purge'"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence in the risk assessment (0.0-1.0)"
    )


class RedactResponseWithRisk(BaseModel):
    """Extended redaction response including risk analysis."""
    original_length: int
    redacted_text: str
    entities_found: list[str]
    policy_applied: Optional[PolicyResponse] = Field(
        None,
        description="Policy that was applied to this request"
    )
    risk_analysis: Optional[RiskAnalysis] = Field(
        None,
        description="Risk analysis from LLM auditor (available after background processing)"
    )


# Restoration Schemas

class RestoreRequest(BaseModel):
    """Request body for restoration endpoint."""
    redacted_text: str = Field(
        ...,
        example="Contact [REDACTED_a1b2] at [REDACTED_c3d4]",
        description="Text containing redaction tokens"
    )


class RestoreResponse(BaseModel):
    """Response from restoration endpoint (Issue 4: includes missing token warnings)."""
    request_id: uuid.UUID = Field(
        ...,
        description="Unique request ID for audit trail"
    )
    original_text: str = Field(
        ...,
        description="Restored text with PII"
    )
    tokens_restored: int = Field(
        ...,
        description="Number of tokens successfully restored"
    )
    tokens_missing: int = Field(
        0,
        description="Number of expired/missing tokens"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Warning messages for missing/expired tokens"
    )
    audit_logged: bool = Field(
        ...,
        description="Whether request was logged to audit trail"
    )


# API Key Management Schemas

class APIKeyCreateRequest(BaseModel):
    """Request to create a new API key."""
    service_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        example="customer-portal"
    )
    description: Optional[str] = Field(
        None,
        example="API key for customer portal restoration"
    )


class APIKeyCreateResponse(BaseModel):
    """Response after creating API key."""
    api_key: str = Field(
        ...,
        description="Raw API key - SAVE THIS! It won't be shown again"
    )
    key_id: uuid.UUID = Field(
        ...,
        description="Key ID for management"
    )
    service_name: str
    created_at: datetime
    warning: str = Field(
        default="IMPORTANT: Save this API key now. You won't be able to see it again!"
    )


class APIKeyInfo(BaseModel):
    """Information about an API key (without the raw key)."""
    key_id: uuid.UUID
    service_name: str
    description: Optional[str]
    created_at: datetime
    revoked: bool
    revoked_at: Optional[datetime]
    last_used_at: Optional[datetime]
    usage_count: int


class APIKeyListResponse(BaseModel):
    """List of API keys."""
    keys: List[APIKeyInfo]
    total: int


# Audit Log Schemas

class AuditLogEntry(BaseModel):
    """Single audit log entry."""
    id: uuid.UUID
    request_id: uuid.UUID
    service_name: str
    timestamp: datetime
    redacted_text: str
    restored_text: Optional[str]
    token_count: int
    success: bool
    error_message: Optional[str]
    ip_address: Optional[str]


class AuditLogResponse(BaseModel):
    """Response with audit log entries."""
    logs: List[AuditLogEntry]
    total: int
    limit: int
    offset: int


# Policy Recommendation Schemas (GenAI Enhancement)

class PolicySuggestionRequest(BaseModel):
    """Request for policy suggestion."""
    text: str = Field(
        ...,
        min_length=1,
        example="Patient John Doe, DOB: 1990-05-15, diagnosis: hypertension",
        description="Text to analyze for policy recommendation"
    )


class PolicySuggestionResponse(BaseModel):
    """Response with policy recommendation from LLM."""
    recommended_context: str = Field(
        ...,
        description="Recommended policy context (general, healthcare, finance)"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence in the recommendation (0.0-1.0)"
    )
    reasoning: str = Field(
        ...,
        description="Explanation of why this policy was chosen"
    )
    detected_domains: List[str] = Field(
        ...,
        description="List of domains detected in the text"
    )
    alternative_contexts: List[str] = Field(
        default_factory=list,
        description="Alternative policy contexts that could be used"
    )
    risk_warning: Optional[str] = Field(
        None,
        description="Warning if text contains cross-domain PII"
    )