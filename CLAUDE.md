# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Project Name**: Sentinel (internal codename in `pyproject.toml`), deployed as PII-project

This is an AI-powered PII (Personally Identifiable Information) redaction gateway built with FastAPI. It uses a three-layer security model:
1. **Primary Layer**: Microsoft Presidio (NLP-based) for PII detection and redaction
2. **Policy Layer**: Context-aware policy engine for HIPAA, PCI-DSS, and GDPR compliance
3. **Verification Layer**: LLM-based auditor (Phi-3 via Ollama) that validates redaction quality and purges Redis tokens if leaks are detected

**Package Management**: This project is managed with [uv](https://github.com/astral-sh/uv), a fast Python package installer and resolver. All dependency management commands should use `uv` instead of pip.

## Architecture

### Core Components

**app/main.py** - FastAPI application with endpoints:
- `POST /redact` - Redacts PII and queues background audit
- `POST /restore` - **[AUTHENTICATED]** Restores original text from Redis tokens (requires X-API-Key header)
- `GET /policies` - Returns available policy contexts and configurations
- `GET /metrics` - Prometheus metrics endpoint
- `POST /admin/api-keys` - Create new API key for restoration access
- `GET /admin/api-keys` - List all API keys (without raw key values)
- `DELETE /admin/api-keys/{key_id}` - Revoke an API key
- `GET /admin/audit-logs` - Query restoration audit logs with filtering

**app/service.py** - `RedactorService` class:
- Uses Presidio Analyzer to detect PII entities
- Uses Presidio Anonymizer with custom operator to replace PII with `[REDACTED_xxxx]` tokens
- Stores original PII values in Redis with 24hr expiry (key=token, value=original_text)
- `redact_and_store()` returns: (redacted_text, confidence_scores, created_keys_list)
- `restore()` uses regex to find tokens and swap them back with Redis values

**app/verification.py** - `VerificationAgent` class:
- Sends redacted text to Ollama API (Phi-3 model) for leak detection
- Returns JSON: `{"leaked": true/false, "reason": "explanation"}`
- Called asynchronously in background after redaction completes

**app/schemas.py** - Pydantic models for request/response validation

**app/database.py** - SQLAlchemy async ORM models:
- `APIKey` - API key storage with SHA-256 hashing, usage tracking, and revocation
- `RestorationAuditLog` - Audit trail for all restoration requests with metadata
- `get_session()` - FastAPI dependency for database sessions
- `init_database()` - Initialize database schema

**app/auth.py** - Authentication service:
- `generate_api_key()` - Generate 64-char hex API key with SHA-256 hash
- `validate_api_key()` - FastAPI dependency to validate X-API-Key header
- Updates last_used_at and usage_count on each request
- Raises HTTPException(401) for invalid/revoked keys

**app/audit.py** - Audit logging service:
- `log_restoration_request()` - Log restoration attempts (success/failure)
- `get_audit_logs()` - Query audit logs with filtering and pagination
- Tracks: request_id, service_name, timestamps, IP addresses, user agents, token counts

**app/config.py** - Centralized configuration management:
- Uses pydantic-settings for type-safe configuration
- All settings configurable via environment variables (.env file)
- Redis, PostgreSQL, Ollama, Presidio, authentication, and prompt settings

**app/prompts/** - Advanced LLM prompt engineering:
- `verification_prompts.py`: 4 prompt versions (v1_basic, v2_cot, v3_few_shot, v4_optimized)
- `few_shot_examples.py`: 7 curated examples for few-shot learning
- Configurable prompt selection for A/B testing

**app/policies.py** - Policy Engine for context-aware redaction:
- `RedactionPolicy` dataclass: Defines entity filtering, confidence thresholds, and restoration controls
- `PolicyEngine` class: Manages policy loading, merging, and entity filtering
- Predefined policies: `GENERAL_POLICY`, `HEALTHCARE_POLICY`, `FINANCE_POLICY`
- Policy methods:
  - `load_policy(context)`: Load predefined policy by context name
  - `merge_policies(global_policy, request_policy)`: Merge request overrides with global policy
  - `filter_entities(analyzer_results, policy)`: Filter PII entities based on policy rules
  - `register_policy(policy)`: Register custom policies

**app/policy_schemas.py** - Pydantic models for policy API:
- `PolicyRequest`: Request body schema for policy overrides in `/redact`
- `PolicyResponse`: Response schema with applied policy metadata
- `AvailablePoliciesResponse`: Response schema for `GET /policies` endpoint

### Data Flow

**Redaction Flow (Policy-Aware):**
1. User sends text to `/redact` with optional policy overrides
2. Policy engine loads context (general/healthcare/finance) and merges request overrides
3. Presidio analyzes text and detects all PII entities
4. Policy engine filters entities based on:
   - Enabled/disabled entity types
   - Minimum confidence threshold
5. Presidio redacts filtered PII, storing mappings in Redis with policy metadata
6. Response returns immediately with:
   - Redacted text with `[REDACTED_xxxx]` tokens
   - Policy metadata (context, restoration_allowed, entities_filtered)
   - Confidence scores
7. Background task sends redacted text to LLM auditor
8. If LLM detects leaked PII, it purges all Redis keys created in that request
9. Prometheus metrics track redaction counts and confidence scores

**Restoration Flow (Authenticated):**
1. User sends redacted text to `/restore` with X-API-Key header
2. System validates API key against PostgreSQL (SHA-256 hash lookup)
3. If invalid/revoked, returns HTTP 401
4. System checks policy metadata for each token in Redis
5. If policy blocks restoration, returns HTTP 403 and logs failure to audit trail
6. If allowed, restores PII from Redis and returns original text
7. System logs successful restoration to PostgreSQL audit trail with:
   - request_id, service_name, timestamp, IP address, user agent
   - redacted_text, restored_text, token_count, success status
8. System updates API key's last_used_at and usage_count

### Infrastructure (Docker Compose)

- **api**: FastAPI app on port 8000
- **redis**: Token storage on port 6379
- **postgres**: PostgreSQL 16 database on port 5432 (API keys and audit logs)
- **ollama**: LLM inference server on port 11434
- **prometheus**: Metrics collection on port 9090
- **grafana**: Visualization dashboard on port 3000 (admin/admin)

## Testing & Evaluation

### Test Suite (85% Coverage)

**Location**: `tests/` directory with 2,159 lines of test code across multiple test files

**Test Results** (as of 2026-01-10):
- ✅ **99/99 tests passing** (100% pass rate)
- 📊 **Coverage: 85.36%** (exceeds 60% requirement)
- ⏱️ **Runtime: ~16 seconds**

**Coverage Breakdown**:
- 100% Coverage: `audit.py`, `policies.py`, `policy_schemas.py`, `schemas.py`, `service.py`
- 93% Coverage: `verification.py`
- 91% Coverage: `database.py`
- 89% Coverage: `few_shot_examples.py`
- 88% Coverage: `config.py`
- 79% Coverage: `main.py`

**Structure**:
- `tests/conftest.py` - Shared fixtures (mock Redis with fakeredis, mock Ollama with respx, async SQLite for DB tests, FastAPI dependency overrides)

**Unit Tests** (`tests/unit/`):
- `test_service.py` - RedactorService tests (15 tests)
- `test_verification.py` - VerificationAgent tests (10 tests)
- `test_auth.py` - Authentication service tests (6 tests)
- `test_audit.py` - Audit logging service tests (7 tests)
- `test_policies.py` - **Policy Engine tests** (24 tests - comprehensive coverage):
  - Policy loading and context validation
  - Entity filtering with enabled/disabled lists
  - Confidence threshold filtering
  - Policy merging with request overrides
  - Custom policy registration

**Integration Tests** (`tests/integration/`):
- `test_api.py` - API endpoint tests (14 tests)
- `test_authenticated_restore.py` - Authenticated restore and admin endpoints (9 tests)
- `test_policy_api.py` - **Policy API endpoint tests** (14 tests):
  - GET /policies endpoint
  - Policy overrides in /redact requests
  - Policy-based restoration blocking
  - Policy metadata in responses

**Run tests**:
```bash
# All tests with coverage
uv run pytest --cov=app --cov-report=html --cov-report=term

# Specific test file
uv run pytest tests/unit/test_service.py -v

# View coverage report
open htmlcov/index.html

# Quick run (quiet mode)
uv run pytest --cov=app --cov-report=term -q
```

### Evaluation Framework

**Location**: `evaluation/` directory

**Components**:
- `datasets.py` - 43 benchmark test cases with ground truth annotations
  - 7 PII entity types (EMAIL, PHONE, PERSON, LOCATION, SSN, DATE, IP)
  - 6 categories (standard, edge cases, negative, ambiguous, multiple, context)
- `metrics.py` - Calculate precision, recall, F1, latency (P50/P95/P99)
- `evaluate.py` - Main evaluation runner
- `baseline_comparison.py` - Compare Presidio vs regex-only detection

**Run evaluation**:
```bash
# Full evaluation (requires Redis and Ollama running)
uv run python evaluation/evaluate.py

# View dataset statistics
uv run python evaluation/datasets.py

# Compare against baseline
uv run python evaluation/baseline_comparison.py
```

**Results saved to**: `evaluation/results/benchmark_results.json`

## Policy Engine

### Overview

The Policy Engine provides context-aware, compliance-driven PII redaction. It allows fine-grained control over:
- Which entity types to redact (PERSON, EMAIL, SSN, CREDIT_CARD, etc.)
- Minimum confidence thresholds for redaction
- Restoration permissions per policy context
- Compliance with HIPAA, PCI-DSS, and GDPR requirements

### Predefined Policy Contexts

**General Policy** (`context: "general"`):
- **Purpose**: Default policy for general-purpose PII redaction
- **Entities**: 13 types (PERSON, EMAIL_ADDRESS, PHONE_NUMBER, CREDIT_CARD, US_SSN, US_DRIVER_LICENSE, US_PASSPORT, IBAN_CODE, IP_ADDRESS, DATE_TIME, LOCATION, URL, US_BANK_NUMBER)
- **Confidence Threshold**: 0.0 (redact all detected PII)
- **Restoration**: Disabled by default (opt-in required)
- **Compliance**: General data protection

**Healthcare Policy** (`context: "healthcare"`):
- **Purpose**: HIPAA-compliant PHI (Protected Health Information) redaction
- **Entities**: 7 types (PERSON, PHONE_NUMBER, EMAIL_ADDRESS, US_SSN, DATE_TIME, LOCATION, IP_ADDRESS)
- **Confidence Threshold**: 0.5 (stricter detection to reduce false positives)
- **Restoration**: Disabled (irreversible redaction for compliance)
- **Compliance**: HIPAA

**Finance Policy** (`context: "finance"`):
- **Purpose**: PCI-DSS-compliant financial data redaction
- **Entities**: 8 types (PERSON, US_SSN, CREDIT_CARD, IBAN_CODE, PHONE_NUMBER, EMAIL_ADDRESS, US_BANK_NUMBER, US_DRIVER_LICENSE)
- **Confidence Threshold**: 0.6 (high confidence to protect financial PII)
- **Restoration**: Disabled (irreversible redaction for compliance)
- **Compliance**: PCI-DSS

### Using Policies

**Default behavior** (uses general policy with restoration disabled):
```bash
curl -X POST http://localhost:8000/redact \
  -H "Content-Type: application/json" \
  -d '{"text": "My email is john@example.com and SSN is 123-45-6789"}'
```

**Select a policy context**:
```bash
curl -X POST http://localhost:8000/redact \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Patient John Doe, DOB: 1990-05-15, SSN: 123-45-6789",
    "policy": {"context": "healthcare"}
  }'
```

**Override specific policy settings**:
```bash
curl -X POST http://localhost:8000/redact \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Contact: jane@example.com, Phone: 555-1234",
    "policy": {
      "context": "general",
      "enabled_entities": ["EMAIL_ADDRESS", "PHONE_NUMBER"],
      "min_confidence_threshold": 0.7,
      "restoration_allowed": true
    }
  }'
```

**Disable specific entities**:
```bash
curl -X POST http://localhost:8000/redact \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Meeting on 2024-01-15 with John Doe at john@example.com",
    "policy": {
      "context": "general",
      "disabled_entities": ["DATE_TIME"],
      "restoration_allowed": true
    }
  }'
```

**Response includes policy metadata**:
```json
{
  "redacted_text": "Meeting on 2024-01-15 with [REDACTED_a1b2] at [REDACTED_c3d4]",
  "confidence_scores": {"PERSON": 0.95, "EMAIL_ADDRESS": 1.0},
  "policy": {
    "context": "general",
    "restoration_allowed": true,
    "entities_filtered": 2,
    "description": "General purpose policy with custom overrides"
  }
}
```

### List Available Policies

Query all available policy contexts and their configurations:
```bash
curl http://localhost:8000/policies
```

Response:
```json
{
  "available_contexts": ["general", "healthcare", "finance"],
  "default_context": "general",
  "policies": [
    {
      "context": "general",
      "enabled_entities": ["PERSON", "EMAIL_ADDRESS", ...],
      "restoration_allowed": false,
      "min_confidence_threshold": 0.0,
      "description": "General purpose policy - redacts all PII types"
    },
    ...
  ]
}
```

### Policy Enforcement in Restoration

When restoring redacted text, the system checks each token's policy metadata:
- If `restoration_allowed=false` in the original redaction policy, restoration fails with HTTP 403
- If `restoration_allowed=true`, restoration succeeds (with valid API key)
- Policy violations are logged to the audit trail

**Example restoration failure** (policy blocked):
```bash
curl -X POST http://localhost:8000/restore \
  -H "X-API-Key: your_key" \
  -H "Content-Type: application/json" \
  -d '{"redacted_text": "Patient [REDACTED_a1b2]"}'

# Response: 403 Forbidden
{
  "detail": "Restoration not allowed for token [REDACTED_a1b2] due to policy restrictions"
}
```

## Authentication & Audit Trail

### API Key Management

The `/restore` endpoint requires authentication via API key to ensure secure, auditable access to PII restoration.

**Database Initialization:**
```bash
# Initialize PostgreSQL database and create initial admin API key
uv run python scripts/init_db.py

# Save the API key displayed - it cannot be retrieved later!
```

**Creating API Keys:**
```bash
curl -X POST http://localhost:8000/admin/api-keys \
  -H "Content-Type: application/json" \
  -d '{
    "service_name": "customer-portal",
    "description": "Customer portal restoration access"
  }'
```

**Listing API Keys:**
```bash
# List all active keys
curl http://localhost:8000/admin/api-keys

# Include revoked keys
curl http://localhost:8000/admin/api-keys?include_revoked=true
```

**Revoking API Keys:**
```bash
curl -X DELETE http://localhost:8000/admin/api-keys/{key-id}
```

### Using Authenticated Restore

**With API Key:**
```bash
curl -X POST http://localhost:8000/restore \
  -H "X-API-Key: your_64_character_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{"redacted_text": "Contact [REDACTED_a1b2] at [REDACTED_c3d4]"}'
```

**Response includes audit metadata:**
```json
{
  "request_id": "uuid",
  "original_text": "Contact john@example.com at 555-1234",
  "tokens_restored": 2,
  "audit_logged": true
}
```

### Audit Logging

All restoration requests are logged to PostgreSQL with comprehensive metadata:

**Query Audit Logs:**
```bash
# Recent restorations
curl http://localhost:8000/admin/audit-logs?limit=100

# Filter by service
curl http://localhost:8000/admin/audit-logs?service_name=customer-portal

# Pagination
curl http://localhost:8000/admin/audit-logs?limit=50&offset=100
```

**Audit Log Fields:**
- `request_id` - Unique UUID for each restoration request
- `service_name` - Name of service that made the request (from API key)
- `timestamp` - When the request was made
- `redacted_text` - Input text with tokens
- `restored_text` - Output text with PII (null if failed)
- `token_count` - Number of tokens in the request
- `success` - Whether restoration succeeded
- `error_message` - Reason for failure (policy violation, etc.)
- `ip_address` - Client IP address
- `user_agent` - Client user agent

### Policy-Based Restoration Control

**Default Behavior (Opt-In):**
- All policies default to `restoration_allowed=false` for maximum security
- PII redactions are irreversible by default
- Must explicitly enable restoration per policy context

**Policy Contexts:**
- **general**: Default policy (restoration disabled)
- **healthcare**: HIPAA-compliant (restoration disabled)
- **finance**: PCI-DSS-compliant (restoration disabled)

**Enabling Restoration:**
```bash
curl -X POST http://localhost:8000/redact \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Patient: John Doe, SSN: 123-45-6789",
    "policy": {
      "context": "general",
      "restoration_allowed": true
    }
  }'
```

### Security Features

- **API Keys**: 64-character hex keys with SHA-256 hashing
- **Usage Tracking**: Automatic `last_used_at` and `usage_count` updates
- **Revocation**: Instant API key revocation via admin endpoint
- **Audit Trail**: Immutable PostgreSQL logs for compliance (HIPAA, PCI-DSS, GDPR)
- **IP Tracking**: Client IP addresses logged for forensic analysis
- **Policy Enforcement**: Per-token policy validation before restoration

## Development Commands

### Setup
```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies with uv
uv pip install -r requirements.txt

# Download spaCy language model (required for Presidio)
uv run python -m spacy download en_core_web_lg

# Alternative: Sync dependencies from pyproject.toml
uv sync
```

### Running Locally

**With Docker Compose (recommended):**
```bash
# Start all services
docker-compose up --build

# Start in detached mode
docker-compose up -d

# View logs
docker-compose logs -f api

# Stop services
docker-compose down
```

**Without Docker:**
```bash
# Requires Redis running on localhost:6379
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Testing

**Stress test script:**
```bash
# Run after starting services
uv run python stress_test.py
```

This script tests 10 edge cases with tricky PII patterns, waits for LLM auditor, and verifies purge behavior.

**Manual API testing:**
```bash
# Initialize database and get API key (first time only)
uv run python scripts/init_db.py

# Redact text
curl -X POST http://localhost:8000/redact \
  -H "Content-Type: application/json" \
  -d '{"text": "My name is Jane Doe and my email is jane@example.com"}'

# Restore text (requires API key)
curl -X POST http://localhost:8000/restore \
  -H "X-API-Key: your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{"redacted_text": "My name is [REDACTED_abc1] and my email is [REDACTED_xyz9]"}'

# Create API key
curl -X POST http://localhost:8000/admin/api-keys \
  -H "Content-Type: application/json" \
  -d '{"service_name": "test-service", "description": "Test key"}'

# Query audit logs
curl http://localhost:8000/admin/audit-logs?limit=10

# View metrics
curl http://localhost:8000/metrics
```

### Monitoring

- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (admin/admin)
- Metrics tracked:
  - `total_redactions`: Counter for redaction requests
  - `model_confidence_scores`: Histogram of Presidio confidence
  - `auditor_leaks_found_total`: Counter for LLM-detected leaks

## Advanced LLM Prompt Engineering

### Prompt Versions

The system supports 4 prompt versions for systematic optimization:

**v1_basic** (Zero-Shot Baseline):
- Simple instruction-based prompt
- No examples or reasoning steps
- Fast but less accurate

**v2_cot** (Chain-of-Thought):
- Step-by-step reasoning process
- Explicit instructions for each PII category
- Better on complex cases

**v3_few_shot** (Best Performance):
- 7 curated examples showing leaked vs clean text
- Includes analysis for each example
- Expected +15-20% accuracy improvement

**v4_optimized** (Fast Inference):
- Concise version with 2 examples
- Optimized for lower latency
- Good balance of speed and accuracy

### Configuration

Set prompt version in `.env`:
```bash
PROMPT_VERSION=v3_few_shot
FEW_SHOT_EXAMPLES_COUNT=3
USE_CHAIN_OF_THOUGHT=true
```

Or override at runtime:
```python
result = await verifier.check_for_leaks(text, prompt_version="v3_few_shot")
```

## Production Deployment

### Kubernetes Deployment

The project includes production-ready Kubernetes manifests for enterprise deployment.

**Directory Structure**:
- `k8s/base/` - Base Kubernetes manifests
  - `api/` - FastAPI application deployment and service
  - `redis/` - Redis StatefulSet and service
  - `ollama/` - Ollama LLM server deployment
  - `prometheus/` - Monitoring stack
  - `grafana/` - Visualization dashboard
  - `configmaps/` - Configuration management
  - `secrets/` - Secret management (template files, not committed)
  - `ingress/` - Ingress controller configuration
  - `scripts/` - Deployment helper scripts

- `k8s/helm/` - Helm chart for templated deployment
  - `sentinel/` - Helm chart for the Sentinel PII gateway
  - `sentinel/templates/` - Kubernetes resource templates

**Deploying with kubectl**:
```bash
# Apply all base manifests
kubectl apply -f k8s/base/

# Apply specific component
kubectl apply -f k8s/base/api/

# Check deployment status
kubectl get pods -l app=sentinel-api
kubectl get svc sentinel-api
```

**Deploying with Helm**:
```bash
# Install the Helm chart
helm install sentinel k8s/helm/sentinel/ \
  --namespace pii-gateway \
  --create-namespace

# Upgrade deployment
helm upgrade sentinel k8s/helm/sentinel/ \
  --namespace pii-gateway

# Uninstall
helm uninstall sentinel --namespace pii-gateway
```

**Key Components**:
- **API Deployment**: Horizontal Pod Autoscaling (HPA) for traffic spikes
- **Redis StatefulSet**: Persistent storage for PII token mappings
- **PostgreSQL**: External managed database (RDS, Cloud SQL recommended)
- **Ollama**: GPU-enabled nodes for LLM inference
- **Ingress**: TLS termination with cert-manager
- **Monitoring**: Prometheus + Grafana for observability

**Production Considerations**:
- Redis persistence with PVC (Persistent Volume Claims)
- Database connection pooling via SQLAlchemy
- Secret management with Kubernetes Secrets or external secret stores (Vault, AWS Secrets Manager)
- Resource limits and requests configured per workload
- Liveness and readiness probes for all services
- Network policies for inter-service communication

### CI/CD Pipeline

**GitHub Actions Workflows**:

**`.github/workflows/claude.yml`** - Claude Code Integration:
- Triggered by: Issue comments, PR comments, PR reviews mentioning `@claude`
- Permissions: Read code, PRs, issues, CI results
- Automated code review and suggestions via Claude Code
- Example: Comment `@claude review this PR` on any pull request

**`.github/workflows/claude-code-review.yml`** - Automated PR Review:
- Triggered by: Pull request creation, updates
- Runs Claude Code automated review
- Checks code quality, security, and best practices
- Posts review comments directly on PRs

**Triggering Claude Code**:
```bash
# In a GitHub issue or PR comment:
@claude help me fix the authentication bug

# In a PR:
@claude review this code for security issues

# In an issue:
@claude implement feature X based on the description
```

## Key Implementation Details

### Redis Token Management
- Each redaction creates unique tokens: `[REDACTED_<4-char-hex>]`
- `redact_and_store()` returns a list of created keys for that specific request
- If auditor finds a leak, it deletes only those keys (not all Redis data)
- TTL is 86400 seconds (24 hours)

### LLM Auditor Integration
- Runs asynchronously via FastAPI BackgroundTasks
- Does not block the `/redact` response
- Uses Ollama's `/api/generate` endpoint with `stream=False` and `format="json"`
- Robust JSON parsing handles markdown-wrapped responses from LLM

### Presidio Custom Operator
The anonymizer uses a custom lambda operator instead of built-in replacers to generate tokens and store mappings in Redis simultaneously.

## Configuration Files

### Core Configuration

- **`.env.example`** - Environment variable template (commit to repo)
- **`.env`** - Active environment configuration (DO NOT commit, contains secrets)
- **`pyproject.toml`** - Python project metadata and dependencies (managed by uv)
- **`uv.lock`** - Dependency lock file (ensures reproducible builds)
- **`.python-version`** - Python version pinning (3.13+)
- **`requirements.txt`** - Legacy pip requirements (deprecated, use uv)

### Docker & Infrastructure

- **`docker-compose.yml`** - Local development stack (Redis, PostgreSQL, Ollama, Prometheus, Grafana)
- **`dockerfile`** - Container image definition for FastAPI application
- **`prometheus.yml`** - Prometheus scraping configuration (metrics collection)

### Testing

- **`pytest.ini`** - Pytest configuration:
  - Test discovery patterns
  - Coverage settings
  - Async test support
  - Output formatting

### Git & CI/CD

- **`.gitignore`** - Git exclusion patterns:
  - Virtual environments (`.venv/`)
  - Python cache (`__pycache__/`, `*.pyc`)
  - Test artifacts (`htmlcov/`, `.coverage`, `.pytest_cache/`)
  - IDE files (`.vscode/`, `.idea/`)
  - Environment files (`.env`, not `.env.example`)
  - Ollama data (`ollama_data/`)
  - Claude Code cache (`.claude/`)

### Environment Variables

**Key environment variables** (set in `.env`):

**Redis**:
- `REDIS_HOST` - Redis server hostname (default: localhost)
- `REDIS_PORT` - Redis port (default: 6379)
- `REDIS_DB` - Redis database number (default: 0)

**PostgreSQL**:
- `DATABASE_URL` - PostgreSQL connection string (async)
- Example: `postgresql+asyncpg://user:pass@localhost:5432/sentinel`

**Ollama**:
- `OLLAMA_BASE_URL` - Ollama API endpoint (default: http://localhost:11434)
- `OLLAMA_MODEL` - LLM model name (default: phi3)

**Presidio**:
- `SPACY_MODEL` - spaCy language model (default: en_core_web_lg)

**Authentication**:
- `API_KEY_SECRET` - Secret for API key generation (generate with `openssl rand -hex 32`)

**Prompt Configuration**:
- `PROMPT_VERSION` - LLM prompt version (v1_basic, v2_cot, v3_few_shot, v4_optimized)
- `FEW_SHOT_EXAMPLES_COUNT` - Number of examples for few-shot prompts (default: 3)
- `USE_CHAIN_OF_THOUGHT` - Enable CoT reasoning (default: true)

## Project Structure

### Directory Layout

```
PII-project/
├── app/                    # Core application
│   ├── main.py            # FastAPI endpoints
│   ├── service.py         # Redaction service
│   ├── verification.py    # LLM auditor
│   ├── policies.py        # Policy engine
│   ├── policy_schemas.py  # Policy Pydantic models
│   ├── schemas.py         # Request/response schemas
│   ├── config.py          # Configuration management
│   ├── database.py        # SQLAlchemy models
│   ├── auth.py            # Authentication service
│   ├── audit.py           # Audit logging
│   └── prompts/           # LLM prompt engineering
│       ├── verification_prompts.py
│       └── few_shot_examples.py
├── tests/                 # Test suite (2,159 lines)
│   ├── conftest.py        # Shared fixtures
│   ├── unit/              # Unit tests
│   │   ├── test_service.py
│   │   ├── test_verification.py
│   │   ├── test_auth.py
│   │   ├── test_audit.py
│   │   └── test_policies.py
│   └── integration/       # Integration tests
│       ├── test_api.py
│       ├── test_authenticated_restore.py
│       └── test_policy_api.py
├── evaluation/            # Evaluation framework
│   ├── datasets.py        # 43 benchmark test cases
│   ├── metrics.py         # Precision, recall, F1, latency
│   ├── evaluate.py        # Main evaluation runner
│   ├── baseline_comparison.py
│   └── results/           # Benchmark results
│       └── plots/         # Future: visualization plots
├── scripts/               # Utility scripts
│   └── init_db.py         # Database initialization
├── k8s/                   # Kubernetes deployment
│   ├── base/              # Base manifests
│   │   ├── api/
│   │   ├── redis/
│   │   ├── ollama/
│   │   ├── prometheus/
│   │   ├── grafana/
│   │   ├── configmaps/
│   │   ├── secrets/
│   │   ├── ingress/
│   │   └── scripts/
│   └── helm/              # Helm chart
│       └── sentinel/
├── .github/               # GitHub Actions workflows
│   └── workflows/
│       ├── claude.yml     # Claude Code integration
│       └── claude-code-review.yml
├── docker-compose.yml     # Local development stack
├── dockerfile             # Container image
├── pyproject.toml         # Python project config (uv)
├── uv.lock                # Dependency lock file
├── requirements.txt       # Legacy pip requirements
├── pytest.ini             # Test configuration
├── prometheus.yml         # Monitoring config
├── stress_test.py         # Manual stress testing
├── CLAUDE.md              # Developer guide (this file)
├── README.md              # User documentation
├── .env.example           # Environment template
├── .gitignore             # Git exclusions
└── .python-version        # Python 3.13
```

### Empty Directories (Placeholders)

These directories exist but are currently empty (reserved for future features):
- **`app/security/`** - Future: Additional security utilities
- **`app/monitoring/`** - Future: Custom monitoring code
- **`tests/infrastructure/`** - Future: Infrastructure tests (Docker, K8s)
- **`evaluation/results/plots/`** - Future: Benchmark visualization plots

## Dependencies

Core libraries:
- **fastapi** + **uvicorn**: Web framework and ASGI server
- **presidio-analyzer** + **presidio-anonymizer**: PII detection/redaction
- **spacy** + **en_core_web_lg**: NLP model for Presidio
- **redis**: Token storage (PII mappings)
- **sqlalchemy[asyncio]**: Async ORM for PostgreSQL
- **asyncpg**: PostgreSQL async driver
- **alembic**: Database migrations
- **httpx**: Async HTTP client for Ollama API
- **prometheus-client**: Metrics export
- **pydantic** + **pydantic-settings**: Schema validation and configuration

Testing libraries:
- **pytest** + **pytest-asyncio** + **pytest-cov**: Test framework and coverage
- **fakeredis**: Mock Redis for tests
- **aiosqlite**: In-memory SQLite for database tests
- **respx**: Mock HTTP client for Ollama tests

## Python Version

Requires Python 3.13+ (see `.python-version` and `pyproject.toml`)
