"""
Infrastructure layer for Counterfactual Financial Oracle.

Provides logging, caching, telemetry, security, and resilience patterns.
"""

from .logging import configure_logging, get_logger
from .cache import cache, CacheManager
from .telemetry import (
    setup_telemetry,
    record_debate_metrics,
    record_simulation_metrics,
    APICostTracker,
    tracer
)
from .security import (
    secure_filename,
    validate_file_type,
    validate_file_size,
    create_secure_temp_file,
    sanitize_text,
    cleanup_temp_file,
    SecurityError,
    FileValidationError,
    PathTraversalError
)
from .retry import (
    with_retry,
    RetryConfig,
    CircuitBreaker,
    ResilientAPIClient,
    create_retry_config_for_provider
)

__all__ = [
    # Logging
    "configure_logging",
    "get_logger",
    
    # Cache
    "cache",
    "CacheManager",
    
    # Telemetry
    "setup_telemetry",
    "record_debate_metrics",
    "record_simulation_metrics",
    "APICostTracker",
    "tracer",
    
    # Security
    "secure_filename",
    "validate_file_type",
    "validate_file_size",
    "create_secure_temp_file",
    "sanitize_text",
    "cleanup_temp_file",
    "SecurityError",
    "FileValidationError",
    "PathTraversalError",
    
    # Retry
    "with_retry",
    "RetryConfig",
    "CircuitBreaker",
    "ResilientAPIClient",
    "create_retry_config_for_provider",
]
