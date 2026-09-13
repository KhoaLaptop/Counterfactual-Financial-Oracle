"""
Caching layer with Redis or in-memory fallback.
"""

import hashlib
import json
from typing import Optional, Any, Callable
from functools import wraps
import time
from cachetools import TTLCache
import redis

from ..config import settings
from .logging import get_logger
from .telemetry import CACHE_HITS, CACHE_MISSES

logger = get_logger(__name__)


class CacheBackend:
    """Abstract cache backend interface."""
    
    def get(self, key: str) -> Optional[Any]:
        raise NotImplementedError
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        raise NotImplementedError
    
    def delete(self, key: str) -> None:
        raise NotImplementedError
    
    def clear(self) -> None:
        raise NotImplementedError


class InMemoryCache(CacheBackend):
    """In-memory cache using cachetools."""
    
    def __init__(self, maxsize: int = 1000, ttl: int = 3600):
        self.cache = TTLCache(maxsize=maxsize, ttl=ttl)
    
    def get(self, key: str) -> Optional[Any]:
        value = self.cache.get(key)
        if value is not None:
            CACHE_HITS.labels(cache_type="memory").inc()
        else:
            CACHE_MISSES.labels(cache_type="memory").inc()
        return value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        self.cache[key] = value
    
    def delete(self, key: str) -> None:
        self.cache.pop(key, None)
    
    def clear(self) -> None:
        self.cache.clear()


class RedisCache(CacheBackend):
    """Redis cache backend."""
    
    def __init__(self, redis_url: str):
        self.client = redis.from_url(redis_url, decode_responses=True)
    
    def get(self, key: str) -> Optional[Any]:
        value = self.client.get(key)
        if value is not None:
            CACHE_HITS.labels(cache_type="redis").inc()
            return json.loads(value)
        else:
            CACHE_MISSES.labels(cache_type="redis").inc()
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        serialized = json.dumps(value)
        self.client.setex(key, ttl or settings.cache_ttl_seconds, serialized)
    
    def delete(self, key: str) -> None:
        self.client.delete(key)
    
    def clear(self) -> None:
        self.client.flushdb()


class CacheManager:
    """Manages caching operations with configurable backend."""
    
    def __init__(self):
        self.backend: CacheBackend
        
        if settings.redis_url:
            try:
                self.backend = RedisCache(settings.redis_url)
                logger.info("redis_cache_initialized")
            except Exception as e:
                logger.warning("redis_connection_failed", error=str(e), fallback="memory")
                self.backend = InMemoryCache(
                    maxsize=settings.cache_max_size,
                    ttl=settings.cache_ttl_seconds
                )
        else:
            self.backend = InMemoryCache(
                maxsize=settings.cache_max_size,
                ttl=settings.cache_ttl_seconds
            )
            logger.info("in_memory_cache_initialized")
    
    def _generate_key(self, *args, **kwargs) -> str:
        """Generate a cache key from arguments."""
        key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
        return hashlib.sha256(key_data.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        return self.backend.get(key)
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache."""
        self.backend.set(key, value, ttl)
    
    def cached(self, ttl: Optional[int] = None, key_builder: Optional[Callable] = None):
        """Decorator for caching function results."""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                if not settings.cache_enabled:
                    return func(*args, **kwargs)
                
                # Generate cache key
                if key_builder:
                    cache_key = key_builder(*args, **kwargs)
                else:
                    cache_key = f"{func.__name__}:{self._generate_key(*args, **kwargs)}"
                
                # Try to get from cache
                cached_value = self.get(cache_key)
                if cached_value is not None:
                    logger.debug("cache_hit", key=cache_key[:16])
                    return cached_value
                
                # Execute function and cache result
                result = func(*args, **kwargs)
                self.set(cache_key, result, ttl)
                logger.debug("cache_set", key=cache_key[:16])
                
                return result
            
            return wrapper
        return decorator
    
    def invalidate(self, pattern: str) -> None:
        """Invalidate cache entries matching pattern."""
        # For in-memory cache, we'd need to iterate keys
        # For Redis, we could use SCAN
        logger.info("cache_invalidation_requested", pattern=pattern)


# Global cache instance
cache = CacheManager()
