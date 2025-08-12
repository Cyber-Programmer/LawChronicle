"""
Advanced Rate Limiting and Retry Logic for GPT API calls.
Implements exponential backoff, circuit breaker pattern, and intelligent retry strategies.
"""

import time
import random
import asyncio
from typing import Dict, Any, Callable, Optional, List
from datetime import datetime, timedelta
import logging
from enum import Enum
from dataclasses import dataclass
from utils.gpt_monitor import gpt_monitor

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit is open, requests fail fast
    HALF_OPEN = "half_open"  # Testing if service is back

@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_limit: int = 10
    window_size_seconds: int = 60

@dataclass
class RetryConfig:
    """Configuration for retry logic."""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True

@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    expected_exception: type = Exception

class RateLimiter:
    """Advanced rate limiter with sliding window and burst control."""
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.request_times: List[float] = []
        self.burst_count = 0
        self.last_burst_reset = time.time()
    
    def can_make_request(self) -> bool:
        """Check if a request can be made based on rate limits."""
        current_time = time.time()
        
        # Clean old requests outside window
        self.request_times = [t for t in self.request_times 
                            if current_time - t < self.config.window_size_seconds]
        
        # Check minute limit
        if len(self.request_times) >= self.config.requests_per_minute:
            return False
        
        # Check burst limit
        if current_time - self.last_burst_reset > 1.0:  # Reset burst every second
            self.burst_count = 0
            self.last_burst_reset = current_time
        
        if self.burst_count >= self.config.burst_limit:
            return False
        
        return True
    
    def record_request(self):
        """Record a successful request."""
        current_time = time.time()
        self.request_times.append(current_time)
        self.burst_count += 1
    
    def get_wait_time(self) -> float:
        """Calculate how long to wait before next request."""
        if self.can_make_request():
            return 0.0
        
        if self.request_times:
            oldest_request = min(self.request_times)
            return max(0.0, oldest_request + self.config.window_size_seconds - time.time())
        
        return 0.0

class CircuitBreaker:
    """Circuit breaker pattern implementation."""
    
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.last_success_time = None
    
    def can_execute(self) -> bool:
        """Check if the circuit breaker allows execution."""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.config.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        
        if self.state == CircuitState.HALF_OPEN:
            return True
        
        return False
    
    def on_success(self):
        """Record a successful execution."""
        self.failure_count = 0
        self.last_success_time = time.time()
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
            logger.info("Circuit breaker closed - service recovered")
    
    def on_failure(self, exception: Exception):
        """Record a failed execution."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.CLOSED and self.failure_count >= self.config.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")
        
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            logger.warning("Circuit breaker reopened - service still failing")

class RetryHandler:
    """Handles retry logic with exponential backoff and jitter."""
    
    def __init__(self, config: RetryConfig):
        self.config = config
    
    def get_delay(self, attempt: int) -> float:
        """Calculate delay for retry attempt."""
        delay = min(
            self.config.base_delay * (self.config.exponential_base ** attempt),
            self.config.max_delay
        )
        
        if self.config.jitter:
            delay *= (0.5 + random.random() * 0.5)  # Add 50% jitter
        
        return delay
    
    async def execute_with_retry(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with retry logic."""
        last_exception = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                result = func(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    result = await result
                return result
            
            except Exception as e:
                last_exception = e
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                
                if attempt < self.config.max_retries:
                    delay = self.get_delay(attempt)
                    logger.info(f"Retrying in {delay:.2f} seconds...")
                    await asyncio.sleep(delay)
        
        raise last_exception

class AdvancedRateLimiter:
    """Main class combining rate limiting, circuit breaker, and retry logic."""
    
    def __init__(self, 
                 rate_limit_config: RateLimitConfig = None,
                 retry_config: RetryConfig = None,
                 circuit_config: CircuitBreakerConfig = None):
        
        self.rate_limiter = RateLimiter(rate_limit_config or RateLimitConfig())
        self.retry_handler = RetryHandler(retry_config or RetryConfig())
        self.circuit_breaker = CircuitBreaker(circuit_config or CircuitBreakerConfig())
        
        # Statistics
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "rate_limited_requests": 0,
            "circuit_open_requests": 0,
            "retry_attempts": 0
        }
    
    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with all protection mechanisms."""
        self.stats["total_requests"] += 1
        
        # Check circuit breaker
        if not self.circuit_breaker.can_execute():
            self.stats["circuit_open_requests"] += 1
            raise Exception("Circuit breaker is open - service unavailable")
        
        # Check rate limits
        if not self.rate_limiter.can_make_request():
            wait_time = self.rate_limiter.get_wait_time()
            if wait_time > 0:
                logger.info(f"Rate limited - waiting {wait_time:.2f} seconds")
                await asyncio.sleep(wait_time)
        
        # Execute with retry logic
        try:
            result = await self.retry_handler.execute_with_retry(func, *args, **kwargs)
            
            # Record success
            self.rate_limiter.record_request()
            self.circuit_breaker.on_success()
            self.stats["successful_requests"] += 1
            
            return result
        
        except Exception as e:
            # Record failure
            self.circuit_breaker.on_failure(e)
            self.stats["failed_requests"] += 1
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current statistics."""
        success_rate = (self.stats["successful_requests"] / self.stats["total_requests"] * 100) if self.stats["total_requests"] > 0 else 0
        
        return {
            **self.stats,
            "success_rate_percent": round(success_rate, 2),
            "circuit_state": self.circuit_breaker.state.value,
            "failure_count": self.circuit_breaker.failure_count,
            "current_rate_limit": len(self.rate_limiter.request_times)
        }

# Global instance
advanced_rate_limiter = AdvancedRateLimiter()

def rate_limited_gpt_call(func):
    """Decorator to add rate limiting to GPT functions."""
    def wrapper(*args, **kwargs):
        return asyncio.run(advanced_rate_limiter.execute(func, *args, **kwargs))
    return wrapper

async def rate_limited_gpt_call_async(func):
    """Async decorator to add rate limiting to GPT functions."""
    async def wrapper(*args, **kwargs):
        return await advanced_rate_limiter.execute(func, *args, **kwargs)
    return wrapper

# Example usage
def demo_rate_limiting():
    """Demonstrate rate limiting capabilities."""
    
    def mock_api_call(prompt: str) -> Dict:
        """Mock API call that sometimes fails."""
        time.sleep(0.1)
        
        # Simulate occasional failures
        if random.random() < 0.2:  # 20% failure rate
            raise Exception("API call failed")
        
        return {"result": f"Success: {prompt[:20]}...", "prompt": prompt}
    
    # Test rate limiting
    print("Testing rate limiting...")
    
    for i in range(15):
        try:
            result = asyncio.run(advanced_rate_limiter.execute(mock_api_call, f"Test prompt {i}"))
            print(f"Request {i+1}: Success")
        except Exception as e:
            print(f"Request {i+1}: Failed - {e}")
    
    # Print stats
    stats = advanced_rate_limiter.get_stats()
    print(f"\nFinal Stats: {stats}")

if __name__ == "__main__":
    demo_rate_limiting() 