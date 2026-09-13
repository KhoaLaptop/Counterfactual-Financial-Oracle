"""
Telemetry and metrics collection using OpenTelemetry and Prometheus.
"""

from typing import Optional
from contextlib import contextmanager
import time
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME

from ..config import settings
from .logging import get_logger

logger = get_logger(__name__)

# Prometheus metrics
registry = CollectorRegistry()

# Debate metrics
DEBATE_ROUNDS = Counter(
    'debate_rounds_total',
    'Total number of debate rounds executed',
    ['converged'],
    registry=registry
)

DEBATE_LATENCY = Histogram(
    'debate_duration_seconds',
    'Time spent on AI debate',
    registry=registry
)

# Simulation metrics
SIMULATION_TIME = Histogram(
    'simulation_duration_seconds',
    'Time spent on Monte Carlo simulation',
    ['iterations'],
    registry=registry
)

SIMULATION_RESULTS = Gauge(
    'simulation_median_npv',
    'Median NPV from simulation',
    registry=registry
)

# API metrics
API_CALLS = Counter(
    'api_calls_total',
    'Total API calls by provider',
    ['provider', 'model', 'status'],
    registry=registry
)

API_LATENCY = Histogram(
    'api_latency_seconds',
    'API call latency',
    ['provider', 'model'],
    registry=registry
)

API_COST = Counter(
    'api_cost_dollars',
    'Estimated API cost',
    ['provider', 'model'],
    registry=registry
)

# Document extraction metrics
EXTRACTION_TIME = Histogram(
    'extraction_duration_seconds',
    'Document extraction time',
    ['provider'],
    registry=registry
)

EXTRACTION_PAGES = Histogram(
    'extraction_pages',
    'Number of pages processed',
    registry=registry
)

# Cache metrics
CACHE_HITS = Counter(
    'cache_hits_total',
    'Cache hits',
    ['cache_type'],
    registry=registry
)

CACHE_MISSES = Counter(
    'cache_misses_total',
    'Cache misses',
    ['cache_type'],
    registry=registry
)

# Tracer setup
tracer = trace.get_tracer(__name__)


def setup_telemetry():
    """Initialize OpenTelemetry with Jaeger exporter if configured."""
    if not settings.enable_telemetry:
        return
    
    resource = Resource(attributes={
        SERVICE_NAME: settings.app_name
    })
    
    provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(provider)
    
    if settings.jaeger_endpoint:
        jaeger_exporter = JaegerExporter(
            agent_host_name=settings.jaeger_endpoint,
            agent_port=6831,
        )
        provider.add_span_processor(BatchSpanProcessor(jaeger_exporter))
        logger.info("Jaeger exporter configured", endpoint=settings.jaeger_endpoint)


@contextmanager
def timed_operation(operation_name: str, metric: Histogram, **labels):
    """Context manager for timing operations and recording metrics."""
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        metric.labels(**labels).observe(duration)


class APICostTracker:
    """Track API usage costs."""
    
    # Cost per 1K tokens (approximate)
    PRICING = {
        "openai": {
            "gpt-4-turbo": {"input": 0.01, "output": 0.03},
            "gpt-4": {"input": 0.03, "output": 0.06},
        },
        "deepseek": {
            "DeepSeek-V3.2-Speciale": {"input": 0.001, "output": 0.002},
        },
        "google": {
            "gemini-3.0-pro": {"input": 0.0005, "output": 0.0015},
        },
    }
    
    @classmethod
    def record_usage(cls, provider: str, model: str, input_tokens: int, output_tokens: int):
        """Record API usage and estimate cost."""
        pricing = cls.PRICING.get(provider, {}).get(model, {})
        if pricing:
            input_cost = (input_tokens / 1000) * pricing["input"]
            output_cost = (output_tokens / 1000) * pricing["output"]
            total_cost = input_cost + output_cost
            
            API_COST.labels(provider=provider, model=model).inc(total_cost)
            
            logger.debug(
                "api_cost_recorded",
                provider=provider,
                model=model,
                cost_usd=round(total_cost, 4),
                input_tokens=input_tokens,
                output_tokens=output_tokens
            )


def record_debate_metrics(converged: bool, rounds: int, duration: float):
    """Record debate completion metrics."""
    DEBATE_ROUNDS.labels(converged=str(converged)).inc(rounds)
    DEBATE_LATENCY.observe(duration)
    
    logger.info(
        "debate_completed",
        converged=converged,
        rounds=rounds,
        duration_seconds=round(duration, 2)
    )


def record_simulation_metrics(iterations: int, duration: float, median_npv: float):
    """Record simulation completion metrics."""
    SIMULATION_TIME.labels(iterations=str(iterations)).observe(duration)
    SIMULATION_RESULTS.set(median_npv)
    
    logger.info(
        "simulation_completed",
        iterations=iterations,
        duration_seconds=round(duration, 2),
        median_npv=round(median_npv, 2)
    )
