"""
Async Processing Pipeline for GPT API calls.
Provides concurrent processing of multiple GPT requests for massive performance improvements.
"""

import asyncio
import aiohttp
import json
import time
from typing import List, Dict, Any, Callable, Optional
from concurrent.futures import ThreadPoolExecutor
import logging
from utils.gpt_cache import gpt_cache
from utils.gpt_monitor import gpt_monitor

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AsyncGPTProcessor:
    """Handles concurrent GPT API processing with rate limiting and error handling."""
    
    def __init__(self, max_concurrent: int = 10, rate_limit_per_minute: int = 60):
        self.max_concurrent = max_concurrent
        self.rate_limit_per_minute = rate_limit_per_minute
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.rate_limiter = asyncio.Semaphore(rate_limit_per_minute)
        self.executor = ThreadPoolExecutor(max_workers=max_concurrent)
        
    async def process_batch_async(self, 
                                items: List[Dict], 
                                gpt_function: Callable,
                                batch_size: int = 5) -> List[Dict]:
        """
        Process a batch of items asynchronously.
        
        Args:
            items: List of items to process
            gpt_function: Function that makes GPT API calls
            batch_size: Number of items to process in each batch
            
        Returns:
            List of results in same order as input items
        """
        results = [None] * len(items)
        
        # Create batches
        batches = []
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            batch_indices = list(range(i, min(i + batch_size, len(items))))
            batches.append((batch, batch_indices))
        
        # Process batches concurrently
        tasks = []
        for batch, indices in batches:
            task = asyncio.create_task(
                self._process_single_batch_async(batch, indices, gpt_function, results)
            )
            tasks.append(task)
        
        # Wait for all batches to complete
        await asyncio.gather(*tasks, return_exceptions=True)
        
        return results
    
    async def _process_single_batch_async(self, 
                                        batch: List[Dict], 
                                        indices: List[int],
                                        gpt_function: Callable,
                                        results: List) -> None:
        """Process a single batch asynchronously."""
        async with self.semaphore:
            try:
                # Check cache first
                cached_results = await self._check_cache_async(batch)
                uncached_items = []
                uncached_indices = []
                
                for i, (item, cached_result) in enumerate(zip(batch, cached_results)):
                    if cached_result is not None:
                        results[indices[i]] = cached_result
                    else:
                        uncached_items.append(item)
                        uncached_indices.append(indices[i])
                
                # Process uncached items
                if uncached_items:
                    await self._process_uncached_items_async(
                        uncached_items, uncached_indices, gpt_function, results
                    )
                    
            except Exception as e:
                logger.error(f"Error processing batch: {e}")
                # Mark all items in batch as failed
                for idx in indices:
                    results[idx] = {"error": str(e)}
    
    async def _check_cache_async(self, batch: List[Dict]) -> List[Optional[Dict]]:
        """Check cache for all items in batch asynchronously."""
        async def check_single_cache(item):
            return gpt_cache.get(item.get('prompt', ''))
        
        tasks = [check_single_cache(item) for item in batch]
        return await asyncio.gather(*tasks)
    
    async def _process_uncached_items_async(self, 
                                          items: List[Dict],
                                          indices: List[int],
                                          gpt_function: Callable,
                                          results: List) -> None:
        """Process uncached items with rate limiting."""
        for item, idx in zip(items, indices):
            async with self.rate_limiter:
                try:
                    # Run GPT function in thread pool to avoid blocking
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(
                        self.executor, gpt_function, item.get('prompt', '')
                    )
                    
                    # Cache the result
                    gpt_cache.set(item.get('prompt', ''), result)
                    results[idx] = result
                    
                    # Log success
                    gpt_monitor.log_call("async_api", success=True)
                    
                except Exception as e:
                    logger.error(f"Error processing item {idx}: {e}")
                    results[idx] = {"error": str(e)}
                    gpt_monitor.log_call("async_api", success=False, error=str(e))
                
                # Small delay to respect rate limits
                await asyncio.sleep(0.1)

# Global instance
async_processor = AsyncGPTProcessor()

def process_async(items: List[Dict], gpt_function: Callable, batch_size: int = 5) -> List[Dict]:
    """
    Convenience function to process items asynchronously.
    
    Args:
        items: List of items to process
        gpt_function: Function that makes GPT API calls
        batch_size: Number of items per batch
        
    Returns:
        List of results
    """
    return asyncio.run(async_processor.process_batch_async(items, gpt_function, batch_size))

async def process_async_await(items: List[Dict], gpt_function: Callable, batch_size: int = 5) -> List[Dict]:
    """
    Async version for use in async contexts.
    
    Args:
        items: List of items to process
        gpt_function: Function that makes GPT API calls
        batch_size: Number of items per batch
        
    Returns:
        List of results
    """
    return await async_processor.process_batch_async(items, gpt_function, batch_size)

def async_gpt_call(func):
    """Decorator to make any GPT function async-compatible."""
    def wrapper(*args, **kwargs):
        # If called in async context, return coroutine
        try:
            loop = asyncio.get_running_loop()
            return asyncio.create_task(
                loop.run_in_executor(None, func, *args, **kwargs)
            )
        except RuntimeError:
            # Not in async context, run normally
            return func(*args, **kwargs)
    return wrapper

# Example usage functions
def demo_async_processing():
    """Demonstrate async processing capabilities."""
    
    def mock_gpt_function(prompt: str) -> Dict:
        """Mock GPT function for demonstration."""
        time.sleep(0.1)  # Simulate API call
        return {"result": f"Processed: {prompt[:20]}...", "prompt": prompt}
    
    # Sample items
    items = [
        {"prompt": f"Process item {i}", "id": i} 
        for i in range(20)
    ]
    
    print("Starting async processing...")
    start_time = time.time()
    
    results = process_async(items, mock_gpt_function, batch_size=5)
    
    end_time = time.time()
    print(f"Async processing completed in {end_time - start_time:.2f} seconds")
    print(f"Processed {len(results)} items")
    
    return results

if __name__ == "__main__":
    demo_async_processing() 