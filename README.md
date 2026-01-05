# PII Redaction Gateway

[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/)
[![Test Coverage](https://img.shields.io/badge/coverage-97%25-brightgreen.svg)](htmlcov/index.html)
[![Code Quality](https://img.shields.io/badge/code%20quality-A-brightgreen.svg)](.)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Production-grade PII redaction system combining NLP-based detection with LLM-powered verification.**

A dual-layer security architecture that automatically detects and redacts Personally Identifiable Information (PII) from text, then validates redaction quality using advanced LLM techniques.

---

## 🎯 Key Features

- **🔒 Dual-Layer Security**: Presidio NLP detection + Phi-3 LLM verification
- **🧪 97% Test Coverage**: Comprehensive unit and integration tests
- **📊 Evaluation Framework**: 43 benchmark cases with automated metrics
- **🤖 Advanced LLM Engineering**: Few-shot learning with chain-of-thought reasoning
- **⚡ High Performance**: Async architecture with Redis caching
- **📈 Production Monitoring**: Prometheus metrics + Grafana dashboards
- **🔧 Configurable**: Environment-based configuration for all settings

---

## 📊 Performance Highlights

| Metric | Value |
|--------|-------|
| **Test Coverage** | 97% (39 tests) |
| **Benchmark Dataset** | 43 test cases, 7 entity types |
| **PII Detection** | Emails, Phones, Names, SSNs, Locations, IPs, Dates |
| **Prompt Versions** | 4 (zero-shot → few-shot + CoT) |
| **Expected P95 Latency** | < 2s per request |

### Evaluation Framework
- ✅ **Precision/Recall/F1** metrics with ground truth annotations
- ✅ **Baseline Comparison**: Presidio vs Regex-only detection
- ✅ **Entity-Level Analysis**: Per-type performance breakdown
- ✅ **Latency Tracking**: P50, P95, P99 measurements

---

## 🏗️ Architecture

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│   FastAPI   │─────▶│   Presidio   │─────▶│    Redis    │
│   Gateway   │      │   Analyzer   │      │  (Tokens)   │
└─────────────┘      └──────────────┘      └─────────────┘
       │                                            │
       │             Background Audit               │
       │                    ↓                       │
       │             ┌──────────────┐               │
       └────────────▶│  Phi-3 LLM   │──────────────┘
                     │  (Ollama)    │  (Purge if leak)
                     └──────────────┘
```

### How It Works

1. **Request**: User sends text containing PII to `/redact` endpoint
2. **Detection**: Presidio analyzes text and identifies PII entities (emails, names, phones, etc.)
3. **Redaction**: PII is replaced with tokens like `[REDACTED_a1b2]`
4. **Storage**: Original PII stored in Redis with 24hr TTL, keyed by token
5. **Response**: Redacted text returned immediately to user
6. **Verification**: Background task sends redacted text to LLM for leak detection
7. **Audit**: If LLM finds leaked PII, Redis tokens are purged for security

### Two-Layer Security Model

**Layer 1: Presidio (NLP-Based)**
- Pattern matching + ML models
- High recall for common PII formats
- Fast, deterministic detection

**Layer 2: LLM Auditor (Context-Aware)**
- Few-shot learning with curated examples
- Detects context-dependent leaks
- Catches edge cases missed by NLP

---

## 🚀 Quick Start

### Using Docker Compose (Recommended)

```bash
# Clone the repository
git clone <your-repo-url>
cd PII-project

# Start all services
docker-compose up --build

# The API will be available at http://localhost:8000
```

### Test the API

```bash
# Redact PII from text
curl -X POST http://localhost:8000/redact \
  -H "Content-Type: application/json" \
  -d '{"text": "Contact John Doe at john.doe@example.com or call 555-123-4567"}'

# Response:
# {
#   "redacted_text": "Contact [REDACTED_a1b2] at [REDACTED_c3d4] or call [REDACTED_e5f6]",
#   "confidence_scores": [0.95, 0.89, 0.92],
#   "audit_status": "queued"
# }

# Restore original text
curl -X POST "http://localhost:8000/restore?redacted_text=Contact%20[REDACTED_a1b2]"

# View Prometheus metrics
curl http://localhost:8000/metrics
```

---

## 📦 Installation

### Prerequisites

- Python 3.13+
- Docker & Docker Compose (for full stack)
- Redis (for token storage)
- Ollama with Phi-3 model (for LLM verification)

### Local Development Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Download spaCy language model (required by Presidio)
python -m spacy download en_core_web_lg

# Copy environment configuration
cp .env.example .env

# Start Redis (required)
docker run -d -p 6379:6379 redis:alpine

# Start Ollama (required for LLM verification)
docker run -d -p 11434:11434 ollama/ollama:latest

# Pull Phi-3 model
docker exec -it <ollama-container-id> ollama pull phi3

# Run the application
uvicorn app.main:app --reload
```

---

## 💻 Usage Examples

### Python SDK Usage

```python
import httpx

# Redact PII
async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://localhost:8000/redact",
        json={"text": "My email is alice@example.com"}
    )
    data = response.json()
    print(f"Redacted: {data['redacted_text']}")
    # Output: Redacted: My email is [REDACTED_a1b2]
```

### API Endpoints

#### `POST /redact`
Redacts PII from text and returns redacted version.

**Request:**
```json
{
  "text": "Contact Jane Smith at jane@example.com"
}
```

**Response:**
```json
{
  "redacted_text": "Contact [REDACTED_a1b2] at [REDACTED_c3d4]",
  "confidence_scores": [0.85, 0.95],
  "audit_status": "queued"
}
```

#### `POST /restore`
Restores original text from redacted version (if tokens still valid).

**Request:**
```
?redacted_text=Contact [REDACTED_a1b2]
```

**Response:**
```json
{
  "original_text": "Contact Jane Smith"
}
```

#### `GET /metrics`
Returns Prometheus metrics for monitoring.

---

## 🧪 Testing & Evaluation

### Run Test Suite

```bash
# Run all tests with coverage
pytest --cov=app --cov-report=html --cov-report=term

# Run specific test categories
pytest tests/unit/          # Unit tests only
pytest tests/integration/   # Integration tests only

# View coverage report
open htmlcov/index.html
```

**Current Coverage: 97%**
- `app/main.py`: 92%
- `app/service.py`: 100%
- `app/verification.py`: 100%
- `app/schemas.py`: 100%

### Run Evaluation Framework

```bash
# Run full evaluation on benchmark dataset
python evaluation/evaluate.py

# Compare against baseline
python evaluation/baseline_comparison.py

# View benchmark statistics
python evaluation/datasets.py
```

**Benchmark Dataset:**
- 43 test cases with ground truth annotations
- 7 PII entity types (EMAIL, PHONE, PERSON, LOCATION, SSN, DATE, IP)
- 6 categories (standard, edge cases, negative, ambiguous, multiple, context)

---

## 🤖 LLM Prompt Engineering

### Prompt Versions (Configurable)

The system supports multiple prompt strategies for A/B testing:

#### v1_basic (Zero-Shot Baseline)
```
Simple instruction: "Find PII in this text"
```

#### v2_cot (Chain-of-Thought)
```
Step-by-step reasoning:
1. Scan for names
2. Check emails
3. Find phone numbers
4. Verify redaction
```

#### v3_few_shot (Best Performance)
```
7 curated examples showing:
- Properly redacted text (clean)
- Leaked PII (violations)
- Edge cases (partial leaks)
```

#### v4_optimized (Fast Inference)
```
Concise version with 2 examples
Optimized for lower latency
```

### Configure Prompt Version

```bash
# In .env file
PROMPT_VERSION=v3_few_shot
FEW_SHOT_EXAMPLES_COUNT=3
USE_CHAIN_OF_THOUGHT=true
```

### Expected Improvements

| Prompt Version | Expected Accuracy | Inference Time |
|----------------|-------------------|----------------|
| v1_basic | Baseline | Fast |
| v2_cot | +10% | Medium |
| v3_few_shot | +15-20% | Medium |
| v4_optimized | +12% | Fast |

---

## 🛠️ Technical Stack

### Core Technologies
- **FastAPI** 0.128.0 - High-performance async web framework
- **Presidio Analyzer** 2.2.360 - NLP-based PII detection
- **Presidio Anonymizer** 2.2.360 - PII redaction engine
- **spaCy** 3.8.11 + `en_core_web_lg` - NLP models
- **Redis** 7.1.0 - Token storage with TTL
- **Ollama** (Phi-3) - LLM for verification

### Testing & Evaluation
- **pytest** 8.0+ with async support
- **pytest-cov** - Coverage reporting (97%)
- **fakeredis** - Redis mocking for tests
- **respx** - HTTP mocking for Ollama
- **scikit-learn** - Metrics calculation
- **matplotlib** + **seaborn** - Visualization

### Configuration & Deployment
- **pydantic-settings** - Type-safe configuration
- **Docker** + **Docker Compose** - Containerization
- **Prometheus** + **Grafana** - Monitoring
- **uvicorn** - ASGI server

---

## 📚 Documentation

```
docs/
├── ARCHITECTURE.md     - System design deep dive (TODO)
├── EVALUATION.md       - Evaluation methodology & results (TODO)
├── PROMPTS.md          - Prompt engineering details (TODO)
└── API.md              - API reference (TODO)

# Current Documentation
├── CLAUDE.md           - Developer guide for Claude Code
├── PROGRESS.md         - Transformation progress log
├── TRANSFORMATION_SUMMARY.md - Portfolio highlights
└── README.md           - This file
```

---

## 🔧 Configuration

All settings are configurable via environment variables. See `.env.example`:

```bash
# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_TTL=86400  # 24 hours

# Ollama LLM
OLLAMA_URL=http://ollama:11434/api/generate
OLLAMA_MODEL=phi3
OLLAMA_TIMEOUT=30.0

# Prompt Engineering
PROMPT_VERSION=v3_few_shot
FEW_SHOT_EXAMPLES_COUNT=3

# Presidio
PRESIDIO_SCORE_THRESHOLD=0.0
PRESIDIO_LANGUAGE=en
```

---

## 📈 Monitoring

### Prometheus Metrics

Access metrics at `http://localhost:8000/metrics`

**Available Metrics:**
- `total_redactions` - Counter of redaction requests
- `model_confidence_scores` - Histogram of Presidio confidence
- `auditor_leaks_found_total` - Counter of LLM-detected leaks

### Grafana Dashboards

Access at `http://localhost:3000` (admin/admin)

Pre-configured dashboards for:
- Request rate and latency
- Redaction success rate
- LLM audit results
- Entity detection breakdown

---

## 🔬 Development

### Project Structure

```
PII-project/
├── app/                    # Application code
│   ├── main.py            # FastAPI endpoints
│   ├── service.py         # Presidio redaction logic
│   ├── verification.py    # LLM verification agent
│   ├── schemas.py         # Pydantic models
│   ├── config.py          # Configuration management
│   └── prompts/           # LLM prompt templates
│       ├── verification_prompts.py
│       └── few_shot_examples.py
├── tests/                 # Test suite (97% coverage)
│   ├── conftest.py       # Shared fixtures
│   ├── unit/             # Unit tests
│   └── integration/      # Integration tests
├── evaluation/            # Benchmarking framework
│   ├── datasets.py       # 43 test cases
│   ├── metrics.py        # Metrics calculation
│   ├── evaluate.py       # Evaluation runner
│   └── baseline_comparison.py
├── docker-compose.yml     # Full stack deployment
├── pytest.ini            # Test configuration
├── requirements.txt      # Python dependencies
└── .env.example          # Configuration template
```

### Running Tests During Development

```bash
# Run tests on file save (watch mode)
pytest-watch

# Run specific test file
pytest tests/unit/test_service.py -v

# Run with debugging
pytest --pdb

# Generate coverage report
pytest --cov=app --cov-report=html
```

### Code Quality

```bash
# Format code
black app/ tests/

# Lint code
ruff check app/

# Type checking (if mypy added)
mypy app/
```

---

## 🎯 Future Enhancements

### Planned Features
- [ ] CI/CD pipeline with GitHub Actions
- [ ] Kubernetes deployment manifests
- [ ] Additional LLM models (Claude, GPT-4)
- [ ] Multi-language support (beyond English)
- [ ] Encryption at rest for Redis tokens
- [ ] Rate limiting and authentication
- [ ] Distributed tracing (Jaeger)
- [ ] Real-time metrics dashboard

### Research Directions
- [ ] Fine-tuning Phi-3 on PII detection
- [ ] Ensemble methods (multiple LLMs voting)
- [ ] Active learning for dataset expansion
- [ ] Privacy-preserving ML techniques

---

## 📖 Learning Resources

This project demonstrates:
- **ML Evaluation**: Precision, recall, F1, baseline comparisons
- **LLM Prompt Engineering**: Few-shot learning, chain-of-thought
- **Production ML**: Testing, monitoring, error handling
- **API Design**: FastAPI, async patterns, background tasks
- **System Architecture**: Dual-layer security, Redis caching

**Great for portfolios showcasing:**
- Applied ML/AI Engineering
- LLM/GenAI Specialist skills
- Production systems thinking
- Software engineering rigor

---

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Write tests for new features
4. Ensure tests pass (`pytest`)
5. Maintain >90% coverage
6. Update documentation
7. Submit a pull request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Microsoft Presidio** - PII detection framework
- **Ollama** - Local LLM inference
- **FastAPI** - Modern Python web framework
- **spaCy** - Industrial-strength NLP

---

## 📧 Contact

For questions or feedback about this portfolio project, please open an issue on GitHub.

---

<div align="center">

**Built with ❤️ showcasing ML/AI Engineering & LLM Expertise**

⭐ Star this repo if you find it helpful for your portfolio!

</div>
