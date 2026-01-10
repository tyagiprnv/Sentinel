# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an AI-powered PII (Personally Identifiable Information) redaction gateway built with FastAPI. It uses a two-layer security model:
1. **Primary Layer**: Microsoft Presidio (NLP-based) for PII detection and redaction
2. **Verification Layer**: LLM-based auditor (Phi-3 via Ollama) that validates redaction quality and purges Redis tokens if leaks are detected

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

### Data Flow

**Redaction Flow:**
1. User sends text to `/redact`
2. Presidio analyzes and redacts PII, storing mappings in Redis
3. Response returns immediately with redacted text
4. Background task sends redacted text to LLM auditor
5. If LLM detects leaked PII, it purges all Redis keys created in that request
6. Prometheus metrics track redaction counts and confidence scores

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

### Test Suite (97% Coverage)

**Location**: `tests/` directory with 63 comprehensive tests

**Structure**:
- `tests/conftest.py` - Shared fixtures (mock Redis with fakeredis, mock Ollama with respx, async SQLite for DB tests)
- `tests/unit/test_service.py` - RedactorService tests (15 tests)
- `tests/unit/test_verification.py` - VerificationAgent tests (10 tests)
- `tests/unit/test_auth.py` - Authentication service tests (7 tests)
- `tests/unit/test_audit.py` - Audit logging service tests (8 tests)
- `tests/integration/test_api.py` - API endpoint tests (14 tests)
- `tests/integration/test_authenticated_restore.py` - Authenticated restore and admin endpoints (9 tests)

**Run tests**:
```bash
# All tests with coverage
pytest --cov=app --cov-report=html --cov-report=term

# Specific test file
pytest tests/unit/test_service.py -v

# View coverage report
open htmlcov/index.html
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
python evaluation/evaluate.py

# View dataset statistics
python evaluation/datasets.py

# Compare against baseline
python evaluation/baseline_comparison.py
```

**Results saved to**: `evaluation/results/benchmark_results.json`

## Authentication & Audit Trail

### API Key Management

The `/restore` endpoint requires authentication via API key to ensure secure, auditable access to PII restoration.

**Database Initialization:**
```bash
# Initialize PostgreSQL database and create initial admin API key
python scripts/init_db.py

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
# Install dependencies
pip install -r requirements.txt

# Download spaCy language model (required for Presidio)
python -m spacy download en_core_web_lg
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
python stress_test.py
```

This script tests 10 edge cases with tricky PII patterns, waits for LLM auditor, and verifies purge behavior.

**Manual API testing:**
```bash
# Initialize database and get API key (first time only)
python scripts/init_db.py

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
