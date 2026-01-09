"""
Pydantic schemas for policy requests and responses.
"""

from pydantic import BaseModel, Field
from typing import Optional, List


class PolicyRequest(BaseModel):
    """
    Policy override in request body.

    Allows clients to override global policy settings for
    specific redaction requests.
    """
    context: Optional[str] = Field(
        None,
        description="Policy context (general, healthcare, finance)",
        example="healthcare"
    )
    enabled_entities: Optional[List[str]] = Field(
        None,
        description="List of entity types to redact",
        example=["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER"]
    )
    disabled_entities: Optional[List[str]] = Field(
        None,
        description="List of entity types to NOT redact (takes precedence)",
        example=["DATE_TIME"]
    )
    restoration_allowed: Optional[bool] = Field(
        None,
        description="Whether restoration is allowed for this request",
        example=False
    )
    min_confidence_threshold: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Minimum confidence score for redaction (0.0 to 1.0)",
        example=0.7
    )


class PolicyResponse(BaseModel):
    """
    Policy metadata in response.

    Informs clients which policy was applied to their request.
    """
    context: str = Field(
        ...,
        description="Policy context that was applied",
        example="healthcare"
    )
    restoration_allowed: bool = Field(
        ...,
        description="Whether restoration is allowed",
        example=False
    )
    entities_filtered: int = Field(
        ...,
        description="Number of entity types active in policy",
        example=7
    )
    description: str = Field(
        ...,
        description="Policy description",
        example="Healthcare policy (HIPAA-compliant) - redacts PHI with no restoration"
    )


class AvailablePoliciesResponse(BaseModel):
    """Response model for GET /policies endpoint."""
    available_contexts: List[str] = Field(
        ...,
        description="List of available policy contexts",
        example=["general", "healthcare", "finance"]
    )
    default_context: str = Field(
        ...,
        description="Default policy context",
        example="general"
    )
    policies: List[dict] = Field(
        ...,
        description="Details of each policy"
    )
