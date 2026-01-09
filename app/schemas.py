from pydantic import BaseModel, Field
from typing import Optional
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