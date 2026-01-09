from fastapi import FastAPI, Response, BackgroundTasks, HTTPException
from app.schemas import RedactRequest, RedactResponse
from app.policy_schemas import PolicyResponse, AvailablePoliciesResponse
from app.verification import verifier
from app.service import redactor
from app.policies import PolicyEngine, GENERAL_POLICY, HEALTHCARE_POLICY, FINANCE_POLICY
from app.config import get_settings
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import json

# Initialize policy engine
policy_engine = PolicyEngine()
settings = get_settings()

# NEW METRIC: Track how many times the Auditor finds a leak
AUDITOR_LEAK_DETECTIONS = Counter("auditor_leaks_found_total", "Number of PII leaks caught by the LLM Auditor")

REDACTION_COUNT = Counter("total_redactions", "Number of redactions performed")
CONFIDENCE_HISTOGRAM = Histogram("model_confidence_scores", "Distribution of model confidence", buckets=[0, 0.5, 0.7, 0.8, 0.9, 1.0])

app = FastAPI(title="Iron-Clad AI Gateway", version="1.0.0")

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
            print(f"🚨 SECURITY ALERT: LLM found a leak: {result.get('reason')}")
            
            for key in token_mapping_keys:
                redactor.db.delete(key)
            print(f"🔒 PURGE COMPLETE: Removed {len(token_mapping_keys)} keys from Redis.")
            
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

@app.post("/restore")
async def restore_data(redacted_text: str):
    """
    Restore redacted text from Redis tokens.

    Returns 403 if restoration is blocked by policy.
    """
    try:
        # Check policy before restoration
        original = redactor.restore(redacted_text, check_policy=True)
        return {"original_text": original}
    except PermissionError as e:
        raise HTTPException(
            status_code=403,
            detail=f"Restoration forbidden: {str(e)}"
        )

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

@app.get("/metrics")
def get_metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)