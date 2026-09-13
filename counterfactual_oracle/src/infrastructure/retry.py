"""
Retry logic with exponential backoff and circuit breaker pattern.
"""

import time
import random
from functools import wraps
from typing import TypeVar, Callable, Optional, Type, Tuple
from enum import Enum
from dataclasses import dataclass

from .logging import get_logger
from .telemetry import API_CALLS, API_LATENCY

logger = get_logger(__name__)

T = TypeVar('T')


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    exceptions: Tuple[Type[Exception], ...] = (Exception,)


class CircuitBreaker:
    """Circuit breaker pattern implementation."""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: Type[Exception] = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
    
    def can_execute(self) -> bool:
        """Check if request can be executed."""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                logger.info("circuit_breaker_half_open")
                return True
            return False
        
        return True  # HALF_OPEN
    
    def record_success(self) -> None:
        """Record successful execution."""
        self.failure_count = 0
        self.state = CircuitState.CLOSED
    
    def record_failure(self) -> None:
        """Record failed execution."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.error(
                "circuit_breaker_open",
                failure_count=self.failure_count,
                threshold=self.failure_threshold
            )


def with_retry(config: Optional[RetryConfig] = None):
    """
    Decorator for adding retry logic with exponential backoff.
    
    Args:
        config: Retry configuration
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(config.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except config.exceptions as e:
                    last_exception = e
                    
                    if attempt == config.max_retries:
                        logger.error(
                            "max_retries_exceeded",
                            function=func.__name__,
                            retries=config.max_retries,
                            error=str(e)
                        )
                        raise
                    
                    # Calculate delay with exponential backoff
                    delay = min(
                        config.base_delay * (config.exponential_base ** attempt),
                        config.max_delay
                    )
                    
                    # Add jitter to avoid thundering herd
                    if config.jitter:
                        delay = random.uniform(delay * 0.5, delay * 1.5)
                    
                    logger.warning(
                        "retry_attempt",
                        function=func.__name__,
                        attempt=attempt + 1,
                        max_retries=config.max_retries,
                        delay=round(delay, 2),
                        error=str(e)
                    )
                    
                    time.sleep(delay)
            
            # Should never reach here
            raise last_exception
        
        return wrapper
    return decorator


class ResilientAPIClient:
    """Base class for API clients with retry and circuit breaker support."""
    
    def __init__(
        self,
        provider: str,
        model: str,
        retry_config: Optional[RetryConfig] = None,
        circuit_breaker: Optional[CircuitBreaker] = None
    ):
        self.provider = provider
        self.model = model
        self.retry_config = retry_config or RetryConfig()
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
    
    def execute_with_resilience(
        self,
        operation: Callable[..., T],
        *args,
        **kwargs
    ) -> T:
        """
        Execute an operation with retry and circuit breaker protection.
        
        Args:
            operation: Function to execute
            *args, **kwargs: Arguments to pass to operation
            
        Returns:
            Result of operation
        """
        # Check circuit breaker
        if not self.circuit_breaker.can_execute():
            raise Exception(
                f"Circuit breaker is OPEN for {self.provider}/{self.model}. "
                "Service temporarily unavailable."
            )
        
        start_time = time.time()
        
        try:
            # Execute with retry
            @with_retry(self.retry_config)
            def _execute():
                return operation(*args, **kwargs)
            
            result = _execute()
            
            # Record success
            self.circuit_breaker.record_success()
            API_CALLS.labels(
                provider=self.provider,
                model=self.model,
                status="success"
            ).inc()
            
            return result
            
        except Exception as e:
            # Record failure
            self.circuit_breaker.record_failure()
            API_CALLS.labels(
                provider=self.provider,
                model=self.model,
                status="error"
            ).inc()
            
            raise
        
        finally:
            API_LATENCY.labels(
                provider=self.provider,
                model=self.model
            ).observe(time.time() - start_time)


def create_retry_config_for_provider(provider: str) -> RetryConfig:
    """Create provider-specific retry configuration."""
    from ..config import settings
    
    configs = {
        "landing_ai": RetryConfig(
            max_retries=settings.landing_ai_max_retries,
            base_delay=settings.landing_ai_retry_delay,
            max_delay=30.0,
            exceptions=(Exception,)
        ),
        "deepseek": RetryConfig(
            max_retries=settings.deepseek_max_retries,
            base_delay=2.0,
            max_delay=30.0,
            exceptions=(Exception,)
        ),
        "openai": RetryConfig(
            max_retries=settings.openai_max_retries,
            base_delay=1.0,
            max_delay=20.0,
            exceptions=(Exception,)
        ),
    }
    
    return configs.get(provider, RetryConfig())
