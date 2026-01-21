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
from app.logging_config import get_logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from datetime import datetime, UTC
import uuid
import json
import re
import httpx
import redis

# Initialize logger (Issue 9)
logger = get_logger("api")

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
    logger.info("Database initialized")


def parse_llm_json_response(result_raw: str) -> dict:
    """
    Robust JSON parsing for LLM responses with fallback handling.

    Issue 2 fix: Handles markdown-wrapped JSON, malformed JSON, and non-JSON responses.

    Args:
        result_raw: Raw LLM response (string or dict)

    Returns:
        Parsed dict with at minimum {"leaked": bool, "reason": str}
    """
    try:
        # If already a dict, return as-is
        if isinstance(result_raw, dict):
            return result_raw

        # Clean markdown wrappers
        clean_json = result_raw.strip()
        clean_json = re.sub(r'^```json\s*', '', clean_json)
        clean_json = re.sub(r'\s*```$', '', clean_json)
        clean_json = clean_json.strip()

        # Parse JSON
        result = json.loads(clean_json)

        # Validate expected structure
        if not isinstance(result, dict) or "leaked" not in result:
            return {"leaked": False, "reason": "Invalid response structure", "error": "malformed_response"}

        return result

    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing failed: {e}, raw: {result_raw[:200]}")
        return {"leaked": False, "reason": "JSON parse error", "error": str(e)}

    except Exception as e:
        logger.error(f"Unexpected error parsing LLM response: {e}")
        return {"leaked": False, "reason": "Unexpected parsing error", "error": str(e)}


async def audit_redaction_task(redacted_text: str, token_mapping_keys: list):
    """
    Background task for LLM-based PII leak detection.

    Issue 14 fix: Specific exception handling with structured logging.
    """
    try:
        result_raw = await verifier.check_for_leaks(redacted_text)

        # Issue 2 fix: Use robust JSON parser
        result = parse_llm_json_response(result_raw)

        if result.get("leaked"):
            AUDITOR_LEAK_DETECTIONS.inc() # Update our health dashboard
            logger.warning(f"SECURITY ALERT: LLM detected PII leak: {result.get('reason')}")

            # Purge leaked tokens
            try:
                purged_count = 0
                for key in token_mapping_keys:
                    if redactor.db.delete(key):
                        purged_count += 1
                        redactor.db.delete(f"{key}:policy")

                logger.info(f"Purged {purged_count}/{len(token_mapping_keys)} Redis keys")
            except redis.RedisError as e:
                logger.error(f"Failed to purge Redis keys after leak: {e}")
        else:
            logger.debug("LLM audit passed - no leaks detected")

    except httpx.TimeoutException as e:
        logger.error(
            f"LLM verification timeout ({settings.ollama_timeout}s) - audit incomplete",
            exc_info=e
        )

    except httpx.ConnectError as e:
        logger.error(f"Cannot connect to Ollama service at {settings.ollama_url}", exc_info=e)

    except redis.RedisError as e:
        logger.error(f"Redis error during audit task", exc_info=e)

    except Exception as e:
        logger.exception(f"Unexpected error in background audit", exc_info=e)

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
        # Attempt restoration (Issue 4: returns dict with warnings)
        result = redactor.restore(body.redacted_text, check_policy=True)

        # Log success
        await log_restoration_request(
            session=session,
            request_id=request_id,
            api_key_record=api_key_record,
            redacted_text=body.redacted_text,
            restored_text=result["restored_text"],
            success=True,
            ip_address=ip_address,
            user_agent=user_agent
        )

        return RestoreResponse(
            request_id=request_id,
            original_text=result["restored_text"],
            tokens_restored=result["tokens_found"],
            tokens_missing=len(result["tokens_missing"]),
            warnings=result["warnings"],
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


# ============================================================================
# Health Check Endpoints (Issue 10)
# ============================================================================

@app.get("/health")
async def health_check(session: AsyncSession = Depends(get_session)):
    """
    Health check endpoint for Kubernetes liveness/readiness probes.

    Checks:
    - API server (implicit)
    - Redis connection
    - PostgreSQL connection
    - Ollama service (degraded only, not critical)

    Returns:
        200 OK: All critical systems healthy
        503 Service Unavailable: Critical system down
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat(),
        "version": settings.api_version,
        "checks": {}
    }

    # Check Redis (critical)
    try:
        redactor.db.ping()
        health_status["checks"]["redis"] = {"status": "healthy"}
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        health_status["checks"]["redis"] = {"status": "unhealthy", "error": str(e)}
        health_status["status"] = "unhealthy"

    # Check PostgreSQL (critical)
    try:
        await session.execute(select(1))
        health_status["checks"]["postgres"] = {"status": "healthy"}
    except Exception as e:
        logger.error(f"PostgreSQL health check failed: {e}")
        health_status["checks"]["postgres"] = {"status": "unhealthy", "error": str(e)}
        health_status["status"] = "unhealthy"

    # Check Ollama (non-critical - degraded only)
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(settings.ollama_url.replace("/api/generate", "/api/tags"))
            if response.status_code == 200:
                health_status["checks"]["ollama"] = {"status": "healthy"}
            else:
                health_status["checks"]["ollama"] = {"status": "degraded", "note": "LLM unavailable"}
    except Exception:
        health_status["checks"]["ollama"] = {"status": "degraded", "note": "LLM unavailable"}

    # Return appropriate status code
    if health_status["status"] == "unhealthy":
        raise HTTPException(status_code=503, detail=health_status)

    return health_status


@app.get("/health/live")
async def liveness_probe():
    """Kubernetes liveness probe - API is alive."""
    return {"status": "alive"}


@app.get("/health/ready")
async def readiness_probe(session: AsyncSession = Depends(get_session)):
    """Kubernetes readiness probe - ready to accept traffic."""
    try:
        redactor.db.ping()
        await session.execute(select(1))
        return {"status": "ready"}
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(status_code=503, detail={"status": "not_ready", "error": str(e)})