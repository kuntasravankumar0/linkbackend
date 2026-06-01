"""
Performance optimization — caching layer for frequently accessed data.
Reduces database load and speeds up API responses.
"""
import time
from functools import wraps
from typing import Any, Callable, Dict, Optional
import logging

logger = logging.getLogger(__name__)

# ── In-memory cache with TTL ───────────────────────────────────────────────────
CACHE_TTL = 300  # Cache for 5 minutes
_cache: Dict[str, tuple[Any, float]] = {}


def cache_result(ttl: int = CACHE_TTL):
    """
    Decorator to cache function results for TTL seconds.
    
    Usage:
        @cache_result(ttl=300)
        def get_all_projects(db):
            return expensive_query(db)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            now = time.time()
            
            # Return cached result if still valid
            if cache_key in _cache:
                result, timestamp = _cache[cache_key]
                if now - timestamp < ttl:
                    logger.debug(f"Cache hit: {func.__name__}")
                    return result
            
            # Compute and cache result
            result = func(*args, **kwargs)
            _cache[cache_key] = (result, now)
            logger.debug(f"Cache miss: {func.__name__} (computed in {time.time() - now:.3f}s)")
            return result
        
        return wrapper
    return decorator


def invalidate_cache(pattern: str = None):
    """
    Invalidate cache entries matching pattern.
    
    Usage:
        invalidate_cache("get_all_projects")  # Clear specific cache
        invalidate_cache()                     # Clear all cache
    """
    global _cache
    if pattern is None:
        _cache.clear()
        logger.info("Cache cleared (all entries)")
    else:
        keys_to_delete = [k for k in _cache.keys() if pattern in k]
        for k in keys_to_delete:
            del _cache[k]
        logger.info(f"Cache cleared ({len(keys_to_delete)} entries matching '{pattern}')")


def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics."""
    return {
        "entries": len(_cache),
        "ttl_seconds": CACHE_TTL,
        "keys": list(_cache.keys()),
    }
