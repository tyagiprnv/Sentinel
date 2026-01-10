from typing import Optional
from fastapi import FastAPI, Response, BackgroundTasks, HTTPException, Depends, Request
from app.schemas import (
    RedactRequest, RedactResponse, RestoreRequest, RestoreResponse,
    APIKeyCreateRequest, APIKeyCreateResponse, APIKeyListResponse, APIKeyInfo,
    AuditLogResponse, AuditLogEntry
)
from app.policy_schemas import PolicyResponse, AvailablePoliciesResponse
from app.verification import verifier
from app.service import redactor
from app.policies import PolicyEngine, GENERAL_POLICY, HEALTHCARE_POLICY, FINANCE_POLICY
from app.config import get_settings
from app.database import get_session, init_database, APIKey as APIKeyModel
from app.auth import validate_api_key, generate_api_key
from app.audit import log_restoration_request, get_audit_logs
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from datetime import datetime, UTC
import uuid
import json
import re

# Initialize policy engine
policy_engine = PolicyEngine()
settings = get_settings()

# NEW METRIC: Track how many times the Auditor finds a leak
AUDITOR_LEAK_DETECTIONS = Counter("auditor_leaks_found_total", "Number of PII leaks caught by the LLM Auditor")

REDACTION_COUNT = Counter("total_redactions", "Number of redactions performed")
CONFIDENCE_HISTOGRAM = Histogram("model_confidence_scores", "Distribution of model confidence", buckets=[0, 0.5, 0.7, 0.8, 0.9, 1.0])

app = FastAPI(title="Iron-Clad AI Gateway", version="1.0.0")


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    await init_database()
    print("Database initialized")


async def audit_redaction_task(redacted_text: str, token_mapping_keys: list):
    """
    This runs in the background. It asks the LLM to find leaks.
    If a leak is found, it nukes the Redis record.
    """
    try:
        result_raw = await verifier.check_for_leaks(redacted_text)
        
        # Robust JSON parsing (LLMs sometimes wrap JSON in markdown blocks)
        if isinstance(result_raw, str):
            # Clean markdown if present
            clean_json = result_raw.replace("```json", "").replace("```", "").strip()
            result = json.loads(clean_json)
        else:
            result = result_raw

        if result.get("leaked"):
            AUDITOR_LEAK_DETECTIONS.inc() # Update our health dashboard
            print(f"SECURITY ALERT: LLM found a leak: {result.get('reason')}")
            
            for key in token_mapping_keys:
                redactor.db.delete(key)
            print(f"PURGE COMPLETE: Removed {len(token_mapping_keys)} keys from Redis.")
            
    except Exception as e:
        print(f"Error in background audit: {e}")

@app.post("/redact")
async def redact_data(request: RedactRequest, background_tasks: BackgroundTasks):
    # 1. Determine policy to apply
    if settings.enable_policy_engine:
        # Load default policy based on configuration
        try:
            global_policy = policy_engine.load_policy(settings.default_policy_context)
        except ValueError:
            global_policy = GENERAL_POLICY

        # Merge with request-level policy overrides if provided
        if request.policy and settings.allow_policy_override:
            # Convert PolicyRequest to dict for merging
            policy_dict = request.policy.model_dump(exclude_none=True)

            # If context is specified in request, load that policy as base
            if "context" in policy_dict:
                try:
                    global_policy = policy_engine.load_policy(policy_dict["context"])
                except ValueError:
                    pass  # Use default global_policy if invalid context

            applied_policy = policy_engine.merge_policies(global_policy, policy_dict)
        else:
            applied_policy = global_policy
    else:
        # Policy engine disabled - use general policy
        applied_policy = None

    # 2. Redact and get the keys created for THIS request
    clean_text, scores, keys = redactor.redact_and_store(request.text, policy=applied_policy)

    # 3. Add the audit task to the background queue
    # We pass the 'keys' so the auditor knows exactly what to delete if it finds a leak
    background_tasks.add_task(audit_redaction_task, clean_text, keys)

    # 4. Metrics
    REDACTION_COUNT.inc()
    for score in scores:
        CONFIDENCE_HISTOGRAM.observe(score)

    # 5. Build policy response metadata
    policy_response = None
    if applied_policy:
        policy_response = PolicyResponse(
            context=applied_policy.context,
            restoration_allowed=applied_policy.restoration_allowed,
            entities_filtered=len(applied_policy.enabled_entities) if applied_policy.enabled_entities else 0,
            description=applied_policy.description
        )

    return {
        "redacted_text": clean_text,
        "confidence_scores": scores,
        "audit_status": "queued",
        "policy_applied": policy_response.model_dump() if policy_response else None
    }

@app.post("/restore", response_model=RestoreResponse)
async def restore_data(
    request: Request,
    body: RestoreRequest,
    api_key_record: APIKeyModel = Depends(validate_api_key),
    session: AsyncSession = Depends(get_session)
):
    """
    Restore redacted text from Redis tokens.

    Requires X-API-Key header. All requests logged to audit trail.
    """
    request_id = uuid.uuid4()
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    try:
        # Attempt restoration
        original = redactor.restore(body.redacted_text, check_policy=True)

        # Count tokens
        tokens_restored = len(re.findall(r"\[REDACTED_[a-z0-9]+\]", body.redacted_text))

        # Log success
        await log_restoration_request(
            session=session,
            request_id=request_id,
            api_key_record=api_key_record,
            redacted_text=body.redacted_text,
            restored_text=original,
            success=True,
            ip_address=ip_address,
            user_agent=user_agent
        )

        return RestoreResponse(
            request_id=request_id,
            original_text=original,
            tokens_restored=tokens_restored,
            audit_logged=True
        )

    except PermissionError as e:
        # Policy blocks - log failure
        await log_restoration_request(
            session=session,
            request_id=request_id,
            api_key_record=api_key_record,
            redacted_text=body.redacted_text,
            success=False,
            error_message=f"Policy violation: {str(e)}",
            ip_address=ip_address,
            user_agent=user_agent
        )

        raise HTTPException(status_code=403, detail=f"Restoration forbidden: {str(e)}")

    except Exception as e:
        # Unexpected error - log failure
        await log_restoration_request(
            session=session,
            request_id=request_id,
            api_key_record=api_key_record,
            redacted_text=body.redacted_text,
            success=False,
            error_message=str(e),
            ip_address=ip_address,
            user_agent=user_agent
        )

        raise HTTPException(status_code=500, detail=f"Restoration failed: {str(e)}")

@app.get("/policies", response_model=AvailablePoliciesResponse)
async def get_available_policies():
    """
    Get available policy contexts and their configurations.

    Returns:
        Available policy contexts with details
    """
    policies_detail = []

    for context in policy_engine.get_available_contexts():
        policy = policy_engine.load_policy(context)
        policies_detail.append({
            "context": policy.context,
            "description": policy.description,
            "restoration_allowed": policy.restoration_allowed,
            "min_confidence_threshold": policy.min_confidence_threshold,
            "enabled_entities": policy.enabled_entities
        })

    return AvailablePoliciesResponse(
        available_contexts=policy_engine.get_available_contexts(),
        default_context=settings.default_policy_context,
        policies=policies_detail
    )


# ============================================================================
# API Key Management Endpoints
# ============================================================================

@app.post("/admin/api-keys", response_model=APIKeyCreateResponse)
async def create_api_key(
    request: APIKeyCreateRequest,
    session: AsyncSession = Depends(get_session)
):
    """Create new API key. Raw key shown once!"""
    raw_key, key_hash = generate_api_key()

    api_key = APIKeyModel()
    api_key.id = str(uuid.uuid4())
    api_key.key_hash = key_hash
    api_key.service_name = request.service_name
    api_key.description = request.description
    api_key.created_at = datetime.now(UTC)
    api_key.revoked = False
    api_key.usage_count = 0

    session.add(api_key)
    await session.commit()
    await session.refresh(api_key)

    return APIKeyCreateResponse(
        api_key=raw_key,
        key_id=uuid.UUID(api_key.id),
        service_name=api_key.service_name,
        created_at=api_key.created_at
    )


@app.get("/admin/api-keys", response_model=APIKeyListResponse)
async def list_api_keys(
    include_revoked: bool = False,
    session: AsyncSession = Depends(get_session)
):
    """List all API keys."""
    stmt = select(APIKeyModel)
    if not include_revoked:
        stmt = stmt.where(APIKeyModel.revoked == False)

    result = await session.execute(stmt)
    keys = result.scalars().all()

    key_infos = [
        APIKeyInfo(
            key_id=uuid.UUID(k.id),
            service_name=k.service_name,
            description=k.description,
            created_at=k.created_at,
            revoked=k.revoked,
            revoked_at=k.revoked_at,
            last_used_at=k.last_used_at,
            usage_count=k.usage_count
        )
        for k in keys
    ]

    return APIKeyListResponse(keys=key_infos, total=len(key_infos))


@app.delete("/admin/api-keys/{key_id}")
async def revoke_api_key(
    key_id: uuid.UUID,
    session: AsyncSession = Depends(get_session)
):
    """Revoke an API key."""
    result = await session.execute(
        update(APIKeyModel)
        .where(APIKeyModel.id == str(key_id))
        .values(revoked=True, revoked_at=datetime.now(UTC))
    )

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="API key not found")

    await session.commit()
    return {"message": f"API key {key_id} revoked"}


# ============================================================================
# Audit Log Endpoints
# ============================================================================

@app.get("/admin/audit-logs", response_model=AuditLogResponse)
async def get_audit_log(
    service_name: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_session)
):
    """Query restoration audit logs with filtering and pagination."""
    if limit > 1000:
        limit = 1000

    logs = await get_audit_logs(
        session=session,
        service_name=service_name,
        limit=limit,
        offset=offset
    )

    log_entries = [
        AuditLogEntry(
            id=uuid.UUID(log.id),
            request_id=uuid.UUID(log.request_id),
            service_name=log.service_name,
            timestamp=log.timestamp,
            redacted_text=log.redacted_text,
            restored_text=log.restored_text,
            token_count=log.token_count,
            success=log.success,
            error_message=log.error_message,
            ip_address=log.ip_address
        )
        for log in logs
    ]

    return AuditLogResponse(
        logs=log_entries,
        total=len(log_entries),
        limit=limit,
        offset=offset
    )


@app.get("/metrics")
def get_metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)