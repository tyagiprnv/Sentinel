# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an AI-powered PII (Personally Identifiable Information) redaction gateway built with FastAPI. It uses a two-layer security model:
1. **Primary Layer**: Microsoft Presidio (NLP-based) for PII detection and redaction
2. **Verification Layer**: LLM-based auditor (Phi-3 via Ollama) that validates redaction quality and purges Redis tokens if leaks are detected

## Architecture

### Core Components

**app/main.py** - FastAPI application with three endpoints:
- `POST /redact` - Redacts PII and queues background audit
- `POST /restore` - Restores original text from Redis tokens
- `GET /metrics` - Prometheus metrics endpoint

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

**app/config.py** - Centralized configuration management:
- Uses pydantic-settings for type-safe configuration
- All settings configurable via environment variables (.env file)
- Redis, Ollama, Presidio, and prompt settings

**app/prompts/** - Advanced LLM prompt engineering:
- `verification_prompts.py`: 4 prompt versions (v1_basic, v2_cot, v3_few_shot, v4_optimized)
- `few_shot_examples.py`: 7 curated examples for few-shot learning
- Configurable prompt selection for A/B testing

### Data Flow

1. User sends text to `/redact`
2. Presidio analyzes and redacts PII, storing mappings in Redis
3. Response returns immediately with redacted text
4. Background task sends redacted text to LLM auditor
5. If LLM detects leaked PII, it purges all Redis keys created in that request
6. Prometheus metrics track redaction counts and confidence scores

### Infrastructure (Docker Compose)

- **api**: FastAPI app on port 8000
- **redis**: Token storage on port 6379
- **ollama**: LLM inference server on port 11434
- **prometheus**: Metrics collection on port 9090
- **grafana**: Visualization dashboard on port 3000 (admin/admin)

## Testing & Evaluation

### Test Suite (97% Coverage)

**Location**: `tests/` directory with 39 comprehensive tests

**Structure**:
- `tests/conftest.py` - Shared fixtures (mock Redis with fakeredis, mock Ollama with respx)
- `tests/unit/test_service.py` - RedactorService tests (15 tests)
- `tests/unit/test_verification.py` - VerificationAgent tests (10 tests)
- `tests/integration/test_api.py` - API endpoint tests (14 tests)

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
# Redact text
curl -X POST http://localhost:8000/redact \
  -H "Content-Type: application/json" \
  -d '{"text": "My name is Jane Doe and my email is jane@example.com"}'

# Restore text
curl -X POST http://localhost:8000/restore \
  -d "redacted_text=[REDACTED_abc1] contacted [REDACTED_xyz9]"

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
- **redis**: Token storage
- **httpx**: Async HTTP client for Ollama API
- **prometheus-client**: Metrics export
- **pydantic**: Schema validation

## Python Version

Requires Python 3.13+ (see `.python-version` and `pyproject.toml`)
