"""
Caching utilities for strategy calculations.
"""
import hashlib
import json
from datetime import datetime, timedelta
from functools import wraps
from typing import Any
import logging

logger = logging.getLogger(__name__)

# Simple in-memory cache
_cache: dict[str, tuple[Any, datetime]] = {}
_cache_ttl = timedelta(minutes=15)


def cache_key(*args, **kwargs) -> str:
    """Generate cache key from arguments."""
    key_data = json.dumps({"args": str(args), "kwargs": str(kwargs)}, sort_keys=True)
    return hashlib.md5(key_data.encode()).hexdigest()


def cached(ttl_minutes: int = 15):
    """
    Decorator to cache function results.
    
    Args:
        ttl_minutes: Cache time-to-live in minutes
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = f"{func.__name__}:{cache_key(*args, **kwargs)}"
            
            # Check cache
            if key in _cache:
                value, timestamp = _cache[key]
                if datetime.now() - timestamp < timedelta(minutes=ttl_minutes):
                    logger.debug(f"Cache hit: {func.__name__}")
                    return value
            
            # Calculate and cache
            result = func(*args, **kwargs)
            _cache[key] = (result, datetime.now())
            logger.debug(f"Cache miss: {func.__name__}")
            return result
        
        return wrapper
    return decorator


def invalidate_cache(pattern: str = None):
    """
    Invalidate cache entries.
    
    Args:
        pattern: If provided, only invalidate keys containing this pattern
    """
    global _cache
    if pattern:
        keys_to_remove = [k for k in _cache.keys() if pattern in k]
        for key in keys_to_remove:
            del _cache[key]
        logger.info(f"Invalidated {len(keys_to_remove)} cache entries matching '{pattern}'")
    else:
        _cache.clear()
        logger.info("Invalidated all cache entries")


def get_cache_stats() -> dict:
    """Get cache statistics."""
    now = datetime.now()
    valid_entries = sum(1 for _, (_, ts) in _cache.items() if now - ts < _cache_ttl)
    return {
        "total_entries": len(_cache),
        "valid_entries": valid_entries,
        "expired_entries": len(_cache) - valid_entries
    }
