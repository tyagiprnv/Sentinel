# Sentinel

**Enterprise-grade PII redaction gateway with GenAI-powered intelligence.**

Three-layer security architecture combining NLP detection, policy-based compliance (HIPAA/PCI-DSS/GDPR), and LLM risk scoring. Now with **intelligent policy recommendations** and **nuanced risk assessments** powered by GenAI.

---

## Why Sentinel?

Traditional PII redaction tools lack context awareness and compliance flexibility. Sentinel solves this with:

- **GenAI Intelligence**: Smart policy recommendations and risk-based scoring (0.0-1.0) instead of binary pass/fail
- **Compliance-First Design**: Pre-configured policies for HIPAA, PCI-DSS, and GDPR with automatic domain detection
- **Explainable AI**: Every risk assessment includes reasoning and confidence scores for audit trails
- **Production Security**: API key authentication, immutable audit logs, tiered risk responses (purge/alert/log)
- **Battle-Tested**: 62% test coverage across 127 tests, 43-case benchmark suite, Kubernetes-ready health checks

The design reflects real-world constraints around compliance, reliability, and operational simplicity—enhanced with GenAI capabilities.

---

## GenAI Features 🤖

### 1. Smart Policy Recommendation

Let AI analyze your text and suggest the optimal policy context:

```bash
# Ask AI which policy to use
curl -X POST http://localhost:8000/suggest-policy \
  -H "Content-Type: application/json" \
  -d '{"text": "Patient billing: credit card ending in 1234"}'

# Response:
{
  "recommended_context": "finance",
  "confidence": 0.88,
  "reasoning": "Mixed healthcare and finance data. Finance has stricter thresholds.",
  "detected_domains": ["healthcare", "finance"],
  "risk_warning": "Cross-domain PII detected"
}
```

**Use Cases:**
- **Auto-routing**: Log pipelines automatically select policies
- **Developer onboarding**: No need to understand policy nuances
- **Multi-domain detection**: Handles mixed healthcare + finance data

### 2. Risk-Based Scoring

Replace binary leak detection with nuanced risk assessment:

```bash
# Configure risk thresholds in .env
ENABLE_RISK_SCORING=true
RISK_THRESHOLD_PURGE=0.7   # Critical: purge immediately
RISK_THRESHOLD_ALERT=0.5   # High: alert security team
RISK_THRESHOLD_LOG=0.3     # Medium: log for review
```

**Risk Scores Explained:**
- **0.0-0.3**: Low risk (properly redacted) → allow
- **0.3-0.5**: Medium risk (contextual clues) → log for investigation
- **0.5-0.7**: High risk (format preservation) → alert security team
- **0.7-1.0**: Critical risk (direct PII leak) → purge keys immediately

**Response includes explainability:**
```json
{
  "risk_score": 0.65,
  "risk_factors": ["Format preservation: SSN pattern visible", "Partial SSN exposed"],
  "recommended_action": "alert",
  "confidence": 0.92
}
```

**Benefits:**
- Tune sensitivity without code changes
- Monitor risk trends in Prometheus/Grafana
- Explain decisions for compliance audits
- Adaptive thresholds per use case

---

## Recent Improvements

**GenAI Enhancements** (Latest):
- Risk-based scoring system with configurable thresholds (purge/alert/log)
- Smart policy recommendation endpoint (`/suggest-policy`)
- Multi-domain detection for cross-policy scenarios
- Explainable AI with reasoning and confidence scores
- 28 new tests (127 total), 62% coverage

**Security & Reliability**:
- Token collision prevention: 16-character tokens for 18.4 quintillion unique combinations
- Missing token tracking: Restore endpoint reports warnings for expired tokens
- Robust error handling: Specific exception types for timeout, connection, and Redis errors

**Observability**:
- Prometheus metrics for risk score distribution
- Structured logging with configurable log levels
- Health check endpoints for Kubernetes probes

All changes are backward compatible.

---

## Engineering Tradeoffs & Design Decisions

Sentinel was built as a practical, production-oriented PII redaction gateway. The goal is reliable and explainable behavior rather than fully automated or experimental compliance.

### Why Presidio for Primary Detection

Presidio is used as the primary PII detection layer instead of LLM-based extraction or custom NER models because:

- It produces predictable, deterministic outputs with confidence scores
- Its entity types align well with common compliance requirements (HIPAA, PCI-DSS, GDPR)
- It runs locally, keeping latency low and operational complexity manageable

LLMs are intentionally not used for primary detection due to their non-deterministic behavior and higher cost.

---

### Why LLM Auditing Is Limited

The LLM is used only as a secondary verification step, not as a decision-maker.

- It cannot add or remove redactions
- If uncertainty or leakage is detected, the system defaults to stricter redaction
- It operates on already-redacted text when possible to reduce PII exposure

This limits risk while still catching context-dependent edge cases.

---

### Known Limitations and Tradeoffs

Some problems were intentionally left out of scope:

- No deep semantic inference from indirect or narrative context
- No human approval or dual-control workflows for restoration
- Policies encode technical rules, not legal interpretation
- Only text inputs are supported (no PDFs, images, or scans)

These tradeoffs keep the system simpler and easier to reason about.

---

### Scaling Considerations

At higher traffic levels, Sentinel would require:

- Selective LLM auditing for higher-risk requests only
- Caching of policy evaluations
- Asynchronous or event-driven verification at larger scale
- Basic monitoring for shifts in entity confidence or volume

These optimizations were deferred to keep the reference implementation focused and understandable.

---

### Design Philosophy

Sentinel prioritizes predictable behavior, clear policy control, and secure defaults over aggressive automation.

---

## Three-Layer Security Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                      FastAPI Gateway                         │
│            (Authentication + Audit Logging)                  │
└──────────────────────────────────────────────────────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  Layer 1:       │  │  Layer 2:       │  │  Layer 3:       │
│  NLP Detection  │─▶│  Policy Engine  │─▶│  Risk Scorer    │
│  (Presidio)     │  │  (Compliance)   │  │  (LLM)          │
└─────────────────┘  └─────────────────┘  └─────────────────┘
         │                    │                    │
         └────────────────────┴────────────────────┘
                              ▼
                     ┌─────────────────┐
                     │  Redis Storage  │
                     │  (24hr TTL)     │
                     └─────────────────┘
```

**Layer 1: Detection** - Presidio analyzes text for 13 PII entity types (EMAIL, SSN, CREDIT_CARD, etc.)
**Layer 2: Policy Engine** - Filters entities by compliance context, confidence thresholds, restoration permissions
**Layer 3: Risk Scorer** - LLM assigns risk scores (0.0-1.0), triggers tiered responses (purge/alert/log)

---

## Quick Start

### Docker Compose (Recommended)

```bash
# Clone and start all services (API, Redis, PostgreSQL, Ollama, Prometheus, Grafana)
git clone <your-repo-url> && cd sentinel
docker-compose up --build

# Initialize database and generate admin API key
docker-compose exec api uv run python scripts/init_db.py
# Save the API key displayed - you cannot retrieve it later!
```

### Test the API

```bash
# Redact PII with healthcare policy (HIPAA-compliant)
curl -X POST http://localhost:8000/redact \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Patient John Doe, DOB: 1990-05-15, SSN: 123-45-6789",
    "policy": {"context": "healthcare"}
  }'

# Response:
# {
#   "redacted_text": "Patient [REDACTED_701dac315f3c4753], DOB: [REDACTED_37e3d87ce0724060], SSN: [REDACTED_889083a273ae459f]",
#   "confidence_scores": {"PERSON": 0.95, "DATE_TIME": 0.85, "US_SSN": 1.0},
#   "policy": {
#     "context": "healthcare",
#     "restoration_allowed": false,
#     "entities_filtered": 3
#   }
# }

# Restore original text (requires API key, tracks missing tokens)
curl -X POST http://localhost:8000/restore \
  -H "X-API-Key: your_64_char_api_key" \
  -H "Content-Type: application/json" \
  -d '{"redacted_text": "Patient [REDACTED_701dac315f3c4753]"}'

# Restore response includes warnings for missing/expired tokens:
# {
#   "request_id": "uuid",
#   "original_text": "Patient John Doe",
#   "tokens_restored": 1,
#   "tokens_missing": 0,
#   "warnings": [],
#   "audit_logged": true
# }

# Get AI-powered policy suggestion (GenAI feature)
curl -X POST http://localhost:8000/suggest-policy \
  -H "Content-Type: application/json" \
  -d '{"text": "Patient billing: credit card ending in 1234"}'

# Response:
# {
#   "recommended_context": "finance",
#   "confidence": 0.88,
#   "reasoning": "Mixed healthcare and finance data. Finance has stricter thresholds.",
#   "detected_domains": ["healthcare", "finance"],
#   "risk_warning": "Cross-domain PII detected"
# }
```

---

## Policy Engine: Compliance Made Simple

### Pre-Configured Contexts

**General Policy** - Default, broad PII coverage
- 13 entity types (EMAIL, PHONE, CREDIT_CARD, SSN, etc.)
- Restoration disabled by default (opt-in security)

**Healthcare Policy** - HIPAA-compliant PHI redaction
- 7 entity types (PERSON, DATE_TIME, US_SSN, etc.)
- Min confidence: 0.5 (reduce false positives)
- Restoration permanently disabled

**Finance Policy** - PCI-DSS-compliant financial data
- 8 entity types (CREDIT_CARD, IBAN_CODE, US_BANK_NUMBER, etc.)
- Min confidence: 0.6 (high-security threshold)
- Restoration permanently disabled

### Custom Policy Overrides

```bash
# Disable specific entities (e.g., allow dates in output)
curl -X POST http://localhost:8000/redact \
  -d '{
    "text": "Meeting on 2024-01-15 with john@example.com",
    "policy": {
      "context": "general",
      "disabled_entities": ["DATE_TIME"],
      "restoration_allowed": true
    }
  }'

# Set custom confidence threshold
curl -X POST http://localhost:8000/redact \
  -d '{
    "text": "Contact Jane at jane@example.com",
    "policy": {
      "enabled_entities": ["EMAIL_ADDRESS"],
      "min_confidence_threshold": 0.8
    }
  }'
```

---

## Authentication & Audit Trail

**Secure Restoration**: `/restore` endpoint requires API key authentication

```bash
# Create API key for service
curl -X POST http://localhost:8000/admin/api-keys \
  -d '{"service_name": "customer-portal", "description": "Restore access"}'

# List active keys (hashed, not retrievable)
curl http://localhost:8000/admin/api-keys

# Query audit logs (GDPR/HIPAA compliance)
curl http://localhost:8000/admin/audit-logs?service_name=customer-portal&limit=100

# Revoke key immediately
curl -X DELETE http://localhost:8000/admin/api-keys/{key-id}
```

**Audit Log Fields**: request_id, service_name, timestamp, redacted_text, restored_text, token_count, success, ip_address, user_agent

---

## Installation & Development

### Prerequisites
- Python 3.13+ with [uv](https://github.com/astral-sh/uv) package manager
- Docker & Docker Compose

### Local Setup

```bash
# Install uv (fast Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv pip install -r requirements.txt
uv run python -m spacy download en_core_web_lg

# Start services
docker-compose up -d

# Run the application
uvicorn app.main:app --reload
```

---

## Testing & Quality Assurance

### Test Coverage: 62% (127/127 tests passing)

```bash
# Run full test suite with coverage
uv run pytest --cov=app --cov-report=html --cov-report=term

# Quick run
uv run pytest --cov=app --cov-report=term -q

# Specific test categories
uv run pytest tests/unit/ -v           # Unit tests (71 tests)
uv run pytest tests/integration/ -v    # Integration tests (53 tests)
```

**Coverage Breakdown:**
- 100% Coverage: `policy_prompts.py`, `policy_schemas.py`, `schemas.py`
- 94% Coverage: `logging_config.py`
- 91% Coverage: `database.py`
- 83% Coverage: `policies.py`
- 71% Coverage: `policy_recommendation.py`
- 70% Coverage: `verification.py`
- 62% Coverage: Total (exceeds 60% requirement)

**GenAI Test Suite:**
- 13 unit tests for policy recommendation service
- 10 integration tests for `/suggest-policy` endpoint
- 5 risk scoring tests for verification agent

### Evaluation Framework

```bash
# Run benchmark suite (43 test cases, 7 entity types)
uv run python evaluation/evaluate.py

# Baseline comparison (Presidio vs regex)
uv run python evaluation/baseline_comparison.py
```

**Metrics Tracked:** Precision, Recall, F1-Score, Latency (P50/P95/P99)

---

## LLM Prompt Engineering

### Risk Scoring Prompts (GenAI)

Four prompt versions for nuanced risk assessment:

| Version | Strategy | Output | Best Use Case |
|---------|----------|--------|---------------|
| **v1_basic** | Zero-shot instruction | Risk score + factors | Baseline/fast inference |
| **v2_cot** | Chain-of-thought reasoning | Step-by-step analysis | Complex edge cases |
| **v3_few_shot** | 4 risk examples (low/med/high/critical) | Best accuracy | Production use |
| **v4_optimized** | Concise 3-example | Balanced speed/accuracy | High-throughput scenarios |

**Configure in `.env`:**
```bash
# Enable risk scoring mode
ENABLE_RISK_SCORING=true
PROMPT_VERSION=v3_few_shot

# Tune thresholds
RISK_THRESHOLD_PURGE=0.7
RISK_THRESHOLD_ALERT=0.5
RISK_THRESHOLD_LOG=0.3
```

### Policy Recommendation Prompt

Single comprehensive prompt for domain detection:
- Analyzes text for healthcare/finance/general indicators
- Returns recommended context with confidence and reasoning
- Handles multi-domain scenarios with cross-policy warnings
- Keyword-based fallback when LLM unavailable

---

## Production Deployment

### Docker Deployment

For production deployment, use the included `docker-compose.yml` with appropriate environment configuration:

```bash
# Set production environment variables
cp .env.example .env
# Edit .env with production credentials

# Start all services
docker-compose up -d

# Initialize database
docker-compose exec api uv run python scripts/init_db.py
```

**Production Considerations:**
- Redis persistence for PII token storage
- PostgreSQL with connection pooling via SQLAlchemy
- Secure secret management (environment variables, secret stores)
- Resource limits configured per container
- TLS termination via reverse proxy (nginx, traefik)
- Prometheus + Grafana monitoring stack included

### CI/CD (GitHub Actions)

**`.github/workflows/claude-code-review.yml`** - Automated PR review with Claude Code
**`.github/workflows/claude.yml`** - Issue/PR comment integration (`@claude help me fix X`)

---

## Monitoring & Observability

**Structured Logging**:
- Centralized logging with module-specific loggers
- Timestamps, module names, function names, and line numbers
- Configurable log levels via `LOG_LEVEL` environment variable
- Exception tracking with full stack traces

**Prometheus Metrics** (`http://localhost:8000/metrics`):
- `total_redactions` - Request counter
- `model_confidence_scores` - Presidio confidence histogram
- `auditor_risk_scores` - **[GenAI]** Risk score distribution (0.0-1.0)
- `auditor_risk_actions_total` - **[GenAI]** Actions taken (allow/alert/purge)
- `auditor_risk_confidence` - **[GenAI]** Assessment confidence scores
- `auditor_leaks_found_total` - Legacy leak detection counter

**Grafana Dashboards** (`http://localhost:3000`, admin/admin):
- Request rate and latency
- Redaction success rate
- Entity detection breakdown
- LLM audit results

**Health Checks**:
- `/health` - Returns 503 if critical systems (Redis/PostgreSQL) are down
- `/health/live` - Simple liveness check for Kubernetes
- `/health/ready` - Readiness check ensuring all dependencies are available

---

## API Endpoints

### Core Endpoints
- `POST /redact` - Redact PII with policy-based filtering
- `POST /restore` - **[AUTH]** Restore original text from tokens
- `GET /policies` - List available policy contexts
- `POST /suggest-policy` - **[GenAI]** Get AI-powered policy recommendation
- `GET /metrics` - Prometheus metrics (includes risk score distribution)

### Health & Monitoring
- `GET /health` - Comprehensive health check (Redis, PostgreSQL, Ollama)
- `GET /health/live` - Kubernetes liveness probe
- `GET /health/ready` - Kubernetes readiness probe

### Admin Endpoints
- `POST /admin/api-keys` - Create API key
- `GET /admin/api-keys` - List API keys (hashed)
- `DELETE /admin/api-keys/{id}` - Revoke API key
- `GET /admin/audit-logs` - Query restoration audit trail

---

## Technical Stack

**Core:** FastAPI, Presidio (NLP), Phi-3 LLM (Ollama), Redis, PostgreSQL, SQLAlchemy
**Testing:** pytest (81% coverage), fakeredis, respx, aiosqlite
**Deployment:** Docker, Docker Compose, Kubernetes-ready health checks
**Monitoring:** Prometheus, Grafana, structured logging
**Package Management:** uv (fast Python resolver)

---

## Project Structure

```
PII-project/
├── app/                   # Core application
│   ├── main.py           # FastAPI endpoints + health checks
│   ├── service.py        # Redaction service (singleton pattern)
│   ├── policies.py       # Policy engine
│   ├── verification.py   # LLM auditor
│   ├── database.py       # SQLAlchemy models
│   ├── auth.py           # API key auth
│   ├── audit.py          # Audit logging
│   ├── logging_config.py # Structured logging
│   └── prompts/          # LLM prompt engineering
├── tests/                # 99 tests, 81% coverage
│   ├── unit/            # Unit tests
│   └── integration/     # Integration tests
├── evaluation/           # Benchmark suite (43 cases)
├── scripts/              # Utility scripts
├── .github/workflows/   # CI/CD pipelines
└── docker-compose.yml   # Local development stack
```

---

## Contributing

Contributions welcome! Ensure:
- Tests pass with >80% coverage
- Follow existing code style
- Update documentation for user-facing changes
- Run `uv run pytest --cov=app` before submitting

---

## Acknowledgments

Built with [Microsoft Presidio](https://github.com/microsoft/presidio), [Ollama](https://ollama.ai), and [FastAPI](https://fastapi.tiangolo.com)

---

**Production-ready PII redaction with compliance enforcement. Deploy with confidence.**
