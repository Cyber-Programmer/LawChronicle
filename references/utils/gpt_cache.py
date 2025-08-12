"""
GPT Cache System for LawChronicle

This module provides a robust caching system for GPT API calls to reduce
API usage and improve performance across the entire pipeline.
"""

import hashlib
import json
import os
import time
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class GPTCache:
    """
    Intelligent caching system for GPT API calls with TTL and versioning.
    """
    
    def __init__(self, cache_file: str = "gpt_cache.json", ttl_hours: int = 24):
        self.cache_file = cache_file
        self.ttl_hours = ttl_hours
        self.cache = self.load_cache()
        self.stats = {"hits": 0, "misses": 0, "expired": 0, "total_requests": 0}
    
    def get_cache_key(self, prompt: str, model: str = "gpt-4o") -> str:
        """Generate a unique cache key for the prompt and model."""
        content = f"{model}:{prompt}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def get(self, prompt: str, model: str = "gpt-4o") -> Optional[Dict[str, Any]]:
        """Get cached result if available and not expired."""
        self.stats["total_requests"] += 1
        key = self.get_cache_key(prompt, model)
        
        if key not in self.cache:
            self.stats["misses"] += 1
            return None
        
        cached_item = self.cache[key]
        
        # Check if expired
        if self.is_expired(cached_item):
            del self.cache[key]
            self.stats["expired"] += 1
            self.stats["misses"] += 1
            return None
        
        self.stats["hits"] += 1
        return cached_item["response"]
    
    def set(self, prompt: str, response: Dict[str, Any], model: str = "gpt-4o") -> None:
        """Cache the response with timestamp."""
        key = self.get_cache_key(prompt, model)
        self.cache[key] = {
            "response": response,
            "timestamp": datetime.now().isoformat(),
            "model": model
        }
        self.save_cache()
    
    def is_expired(self, cached_item: Dict[str, Any]) -> bool:
        """Check if cached item has expired."""
        timestamp = datetime.fromisoformat(cached_item["timestamp"])
        return datetime.now() - timestamp > timedelta(hours=self.ttl_hours)
    
    def load_cache(self) -> Dict[str, Any]:
        """Load cache from file."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading cache: {e}")
        return {}
    
    def save_cache(self) -> None:
        """Save cache to file."""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving cache: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        hit_rate = (self.stats["hits"] / self.stats["total_requests"] * 100) if self.stats["total_requests"] > 0 else 0
        return {**self.stats, "hit_rate_percent": round(hit_rate, 2), "cache_size": len(self.cache)}

gpt_cache = GPTCache()

def cached_gpt_call(func):
    """
    Decorator to automatically cache GPT function calls.
    
    Usage:
    @cached_gpt_call
    def gpt_check_version_order(statute_a, statute_b, meta=None):
        # Your GPT call logic here
        pass
    """
    def wrapper(*args, **kwargs):
        # Create a cache key from function name and arguments
        func_name = func.__name__
        args_str = json.dumps(args, sort_keys=True, default=str)
        kwargs_str = json.dumps(kwargs, sort_keys=True, default=str)
        cache_key = f"{func_name}:{args_str}:{kwargs_str}"
        
        # Try to get from cache
        cached_result = gpt_cache.get(cache_key)
        if cached_result:
            return cached_result
        
        # Call the original function
        result = func(*args, **kwargs)
        
        # Cache the result
        gpt_cache.set(cache_key, result)
        
        return result
    
    return wrapper 