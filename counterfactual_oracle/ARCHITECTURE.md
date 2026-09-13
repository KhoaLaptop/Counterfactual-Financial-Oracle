# Counterfactual Financial Oracle - Architecture Documentation

## Overview

This document describes the improved architecture of the Counterfactual Financial Oracle system following the comprehensive refactoring.

## Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│                     Presentation Layer                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Streamlit  │  │    React     │  │    API       │      │
│  │   (app.py)   │  │  (frontend)  │  │  (backend)   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Application Layer                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Debate     │  │  Simulation  │  │  Validation  │      │
│  │    Agent     │  │    Engine    │  │    Agent     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Domain Layer                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │    Models    │  │    Logic     │  │   Parsers    │      │
│  │  (Pydantic)  │  │  (Finance)   │  │  (Extract)   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Infrastructure Layer                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │  Cache   │ │ Telemetry│ │ Security │ │  Retry   │       │
│  │ (Redis/) │ │(Prometheu│ │ (File    │ │(Circuit │       │
│  │ (Memory) │ │  s/Jaeger│ │  Upload) │ │ Breaker) │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
└─────────────────────────────────────────────────────────────┘
```

## Key Improvements

### 1. Configuration Management (`src/config.py`)
- Centralized configuration using Pydantic Settings
- Environment-based configuration with validation
- Type-safe access to all settings
- Automatic `.env` file loading

### 2. Logging (`src/infrastructure/logging.py`)
- Structured logging with `structlog`
- JSON format for production, readable for development
- Contextual logging with request IDs

### 3. Caching (`src/infrastructure/cache.py`)
- Pluggable backend: Redis or in-memory
- TTL-based expiration
- Decorator-based caching for easy use
- Cache metrics via Prometheus

### 4. Security (`src/infrastructure/security.py`)
- Filename sanitization with `werkzeug`
- Path traversal detection
- File type validation with `python-magic`
- File size limits
- Secure temp file handling

### 5. Resilience (`src/infrastructure/retry.py`)
- Exponential backoff with jitter
- Circuit breaker pattern
- Provider-specific retry configurations
- Automatic failure detection and recovery

### 6. Telemetry (`src/infrastructure/telemetry.py`)
- Prometheus metrics for all operations
- OpenTelemetry tracing with Jaeger support
- API cost tracking
- Debate and simulation metrics

### 7. Document Parsing (`src/parsers/`)

#### Extractor (`extractor.py`)
- Handles HTTP communication with Landing AI
- Retry logic with circuit breaker
- Extraction metrics

#### Normalizer (`normalizer.py`)
- Number cleaning from various formats
- Quarterly data detection and annualization
- Field synonym matching
- Currency and percentage handling

#### Mapper (`mapper.py`)
- Maps extracted data to FinancialReport models
- HTML and Markdown table parsing
- Section detection (Income Statement, Balance Sheet, Cash Flow)
- Calculation of derived metrics

#### Validator (`validator.py`)
- Balance sheet equation validation
- Margin and ratio plausibility checks
- Cross-statement consistency
- Issue classification (ERROR/WARNING/INFO)

## Usage Examples

### Using the New Landing AI Client

```python
from counterfactual_oracle.src.agents.landing_ai_refactored import LandingAIClient

client = LandingAIClient()
report = client.extract_data("/path/to/10k.pdf")

# Report is validated automatically
print(f"Revenue: ${report.income_statement.Revenue:,.0f}")
```

### Using Caching

```python
from counterfactual_oracle.src.infrastructure.cache import cache

@cache.cached(ttl=3600)
def expensive_simulation(report, params):
    # This will be cached for 1 hour
    return run_monte_carlo(report, params)
```

### Using Structured Logging

```python
from counterfactual_oracle.src.infrastructure.logging import get_logger

logger = get_logger(__name__)

logger.info(
    "extraction_completed",
    revenue=report.income_statement.Revenue,
    page_count=5
)
# Output: {"event": "extraction_completed", "revenue": 119575, "page_count": 5, "timestamp": "..."}
```

### Using the Refactored Debate Agent

```python
from counterfactual_oracle.src.agents.debate_agent_refactored import DebateAgent

agent = DebateAgent()
result = agent.run_debate(
    report=financial_report,
    simulation=simulation_results,
    params=scenario_params
)

print(f"Converged: {result.converged}")
print(f"Verdict: {result.final_verdict}")
```

## Configuration

Create a `.env` file:

```env
# API Keys
LANDINGAI_API_KEY=your_key
OPENAI_API_KEY=your_key
DEEPSEEK_API_KEY=your_key

# Application
DEBUG=false
ENVIRONMENT=production
LOG_LEVEL=INFO
LOG_FORMAT=json

# Cache
CACHE_ENABLED=true
REDIS_URL=redis://localhost:6379/0

# Telemetry
ENABLE_TELEMETRY=true
JAEGER_ENDPOINT=localhost

# Security
MAX_PDF_SIZE_MB=50
```

## Testing

Run the test suite:

```bash
# Run all tests
pytest counterfactual_oracle/tests -v

# Run with coverage
pytest counterfactual_oracle/tests --cov=counterfactual_oracle/src --cov-report=html

# Run specific test file
pytest counterfactual_oracle/tests/test_parsers.py -v

# Run security checks
bandit -r counterfactual_oracle/src

# Run type checks
mypy counterfactual_oracle/src
```

## Migration Guide

### From Old to New Landing AI Client

Old code:
```python
from src.agents.landing_ai import LandingAIClient

client = LandingAIClient(api_key="key")
report = client.extract_data("file.pdf")
```

New code:
```python
from src.agents.landing_ai_refactored import LandingAIClient

client = LandingAIClient()  # API key from settings
report = client.extract_data("file.pdf")  # With validation
```

### From Old to New Debate Agent

Old code:
```python
from src.agents.debate_agent import DebateAgent

agent = DebateAgent(openai_key, deepseek_key)
result = agent.run_debate(report, simulation, params)
```

New code:
```python
from src.agents.debate_agent_refactored import DebateAgent

agent = DebateAgent()  # Keys from settings
result = agent.run_debate(report, simulation, params)  # With caching, telemetry
```

## Performance Considerations

### Caching Strategy
- Simulation results cached by input hash
- Debate results cached for identical scenarios
- Cache TTL: 1 hour by default
- In-memory fallback if Redis unavailable

### Async Operations
- Debate can run asynchronously for non-blocking UI
- Use `run_debate_async()` for async execution
- Thread pool for CPU-bound operations

### Resource Limits
- PDF size: 50MB default
- API timeouts: Configured per provider
- Circuit breaker: 3 failures before opening
- Max debate rounds: 10 (configurable)

## Monitoring

### Key Metrics
- `debate_rounds_total`: Number of debate rounds
- `debate_duration_seconds`: Time spent debating
- `simulation_duration_seconds`: Monte Carlo time
- `api_calls_total`: API calls by provider
- `api_cost_dollars`: Estimated API costs
- `cache_hits_total` / `cache_misses_total`: Cache performance

### Alerts
- Circuit breaker open
- High API error rates
- Validation failures
- Cache hit ratio < 80%

## Security Checklist

- [ ] API keys in environment variables
- [ ] File uploads validated (size, type, name)
- [ ] Path traversal prevention
- [ ] Input sanitization
- [ ] No secrets in logs
- [ ] Encrypted temp files (if enabled)
- [ ] Rate limiting on APIs
