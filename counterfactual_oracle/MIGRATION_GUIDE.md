# Migration Guide: Counterfactual Financial Oracle v3.0

This guide helps you migrate from the old codebase to the new refactored architecture.

## Quick Start

The new code maintains backward compatibility while providing better security, performance, and observability.

### 1. Update Dependencies

```bash
pip install -r counterfactual_oracle/requirements.txt
```

New dependencies include:
- `pydantic-settings` - Configuration management
- `structlog` - Structured logging
- `cachetools` + `redis` - Caching
- `prometheus-client` - Metrics
- `opentelemetry-*` - Distributed tracing
- `tenacity` - Retry logic
- `python-magic` - File type validation
- `werkzeug` - Security utilities

### 2. Update Environment Variables

Add to your `.env` file:

```bash
# Application
DEBUG=false
ENVIRONMENT=production
LOG_LEVEL=INFO
LOG_FORMAT=json

# Caching
CACHE_ENABLED=true
# REDIS_URL=redis://localhost:6379/0  # Optional

# Telemetry
ENABLE_TELEMETRY=true
# JAEGER_ENDPOINT=localhost  # Optional

# Security
MAX_PDF_SIZE_MB=50
```

## Code Migration

### Landing AI Client

#### Before (Old)

```python
from src.agents.landing_ai import LandingAIClient
import os

client = LandingAIClient(api_key=os.getenv("LANDINGAI_API_KEY"))
report = client.extract_data("document.pdf")
```

#### After (New)

```python
from src.agents.landing_ai_refactored import LandingAIClient

# API key automatically loaded from settings
client = LandingAIClient()

# Extraction now includes validation
try:
    report = client.extract_data("document.pdf")
except FileValidationError as e:
    print(f"Validation failed: {e}")
```

**Key Changes:**
- Automatic validation of extracted data
- Better error messages
- Retry logic with circuit breaker
- Security checks on file uploads

### Debate Agent

#### Before (Old)

```python
from src.agents.debate_agent import DebateAgent

agent = DebateAgent(
    openai_api_key=os.getenv("OPENAI_API_KEY"),
    deepseek_api_key=os.getenv("DEEPSEEK_API_KEY")
)

result = agent.run_debate(
    report=report,
    simulation=simulation,
    params=params,
    max_rounds=10
)
```

#### After (New)

```python
from src.agents.debate_agent_refactored import DebateAgent

# API keys from settings, with caching and telemetry
agent = DebateAgent()

# Same interface, better performance
result = agent.run_debate(
    report=report,
    simulation=simulation,
    params=params
)

# Or use async version
result = await agent.run_debate_async(
    report=report,
    simulation=simulation,
    params=params
)
```

**Key Changes:**
- Results are cached (same inputs = cached output)
- Metrics automatically recorded
- Better error handling with fallbacks
- Async support available

### Logging

#### Before (Old)

```python
print(f"Extraction completed: {revenue}")
```

#### After (New)

```python
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)

logger.info(
    "extraction_completed",
    revenue=revenue,
    page_count=pages
)
```

**Key Changes:**
- Structured JSON logs in production
- Colored console output in development
- Contextual information automatically added

### Configuration

#### Before (Old)

```python
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("LANDINGAI_API_KEY")
```

#### After (New)

```python
from src.config import settings

# Type-safe access with defaults
api_key = settings.landingai_api_key
timeout = settings.landing_ai_timeout
```

**Key Changes:**
- Type-safe configuration
- Validation and defaults
- Environment-specific settings

### File Upload Security

#### Before (Old)

```python
import tempfile
import os

temp_dir = tempfile.gettempdir()
temp_path = os.path.join(temp_dir, uploaded_file.name)
with open(temp_path, "wb") as f:
    f.write(uploaded_file.getbuffer())
```

#### After (New)

```python
from src.infrastructure.security import (
    create_secure_temp_file,
    cleanup_temp_file,
    FileValidationError
)

try:
    temp_path, safe_name = create_secure_temp_file(uploaded_file)
    # Use temp_path...
finally:
    cleanup_temp_file(temp_path)
```

**Key Changes:**
- Path traversal protection
- File type validation
- File size limits
- Automatic cleanup

### Caching

The new system automatically caches:
- Debate results (1 hour TTL)
- Simulation results (1 hour TTL)

No code changes required - it happens automatically!

To manually use caching:

```python
from src.infrastructure.cache import cache

@cache.cached(ttl=3600)
def my_expensive_function(arg1, arg2):
    return compute(arg1, arg2)
```

### Error Handling

#### Before (Old)

```python
try:
    response = requests.post(url, files=files, timeout=900)
    if response.status_code != 200:
        raise Exception(f"API error: {response.status_code}")
except Exception as e:
    print(f"Error: {e}")
```

#### After (New)

```python
from src.infrastructure.retry import with_retry, RetryConfig

@with_retry(
    RetryConfig(max_retries=3, base_delay=1.0)
)
def call_api():
    # Automatic retry with exponential backoff
    return resilient_client.execute_with_resilience(operation)
```

**Key Changes:**
- Automatic retry with exponential backoff
- Circuit breaker pattern
- Better error classification

## Running Tests

### Old Tests

```bash
pytest counterfactual_oracle/tests/test_ade_parsing.py
```

### New Tests

```bash
# All tests
pytest counterfactual_oracle/tests -v

# Specific modules
pytest counterfactual_oracle/tests/test_parsers.py -v
pytest counterfactual_oracle/tests/test_security.py -v
pytest counterfactual_oracle/tests/test_integration.py -v

# With coverage
pytest counterfactual_oracle/tests --cov=counterfactual_oracle/src
```

## Monitoring

### Prometheus Metrics

The new system exposes metrics on port 9090:

```python
from prometheus_client import start_http_server

# Start metrics server
start_http_server(9090)
```

Available metrics:
- `debate_rounds_total` - Number of debate rounds
- `debate_duration_seconds` - Time spent debating
- `simulation_duration_seconds` - Monte Carlo time
- `api_calls_total` - API calls by provider
- `api_cost_dollars` - Estimated API costs
- `cache_hits_total` / `cache_misses_total`

### Structured Logging

Logs are now JSON in production:

```json
{
  "event": "extraction_completed",
  "revenue": 119575,
  "page_count": 5,
  "timestamp": "2024-01-15T10:30:00Z",
  "logger": "src.parsers.extractor",
  "level": "info"
}
```

## Troubleshooting

### Issue: Cache not working

**Solution:** Check if Redis is running or if `CACHE_ENABLED=true`

```python
from src.config import settings
print(settings.cache_enabled)
print(settings.redis_url)
```

### Issue: API calls failing

**Solution:** Check circuit breaker status

```python
from src.agents.debate_agent_refactored import DebateAgent

agent = DebateAgent()
print(agent.optimist_resilient.circuit_breaker.state)
print(agent.deepseek_resilient.circuit_breaker.state)
```

### Issue: Validation failing

**Solution:** Check validation details

```python
from src.parsers.validator import ExtractionValidator

validator = ExtractionValidator()
result = validator.validate(report)

for issue in result.issues:
    print(f"{issue.severity.value}: {issue.field} - {issue.message}")
```

### Issue: High API costs

**Solution:** Enable caching

```bash
# In .env
CACHE_ENABLED=true
REDIS_URL=redis://localhost:6379/0
```

## Rollback Plan

If you need to rollback:

1. Keep the old files:
   - `src/agents/landing_ai.py` (old)
   - `src/agents/debate_agent.py` (old)

2. Import from old modules:
   ```python
   from src.agents.landing_ai import LandingAIClient  # Old version
   ```

3. The new modules are suffixed with `_refactored.py`

## Support

For issues or questions:
1. Check the ARCHITECTURE.md for detailed documentation
2. Review the integration tests for examples
3. Check logs with structured logging enabled

## Summary of Benefits

| Aspect | Before | After |
|--------|--------|-------|
| **Security** | Basic | Path traversal protection, file validation, sanitization |
| **Reliability** | Basic retries | Circuit breaker, exponential backoff, validation |
| **Performance** | No caching | Redis/in-memory caching, async support |
| **Observability** | Print statements | Structured logging, Prometheus metrics, tracing |
| **Configuration** | dotenv | Pydantic settings with validation |
| **Testing** | Basic | Property-based, integration, security tests |
| **Maintainability** | Monolithic | Modular architecture with clear separation |
