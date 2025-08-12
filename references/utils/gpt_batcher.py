"""
GPT Batch Processing System

This module provides batch processing capabilities for GPT API calls
to reduce the number of individual requests and improve efficiency.
"""

import json
import time
from typing import List, Dict, Any
from utils.gpt_cache import gpt_cache

def batch_gpt_requests(items: List[Dict], gpt_function, batch_size: int = 5):
    """
    Process multiple GPT requests in batches.
    
    Args:
        items: List of items to process
        gpt_function: Function that makes GPT API call
        batch_size: Number of items per batch
    """
    results = []
    
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        
        # Create combined prompt for batch
        combined_prompt = "Process the following items:\n\n"
        for j, item in enumerate(batch, 1):
            combined_prompt += f"Item {j}: {item['prompt']}\n\n"
        
        # Check cache first
        cached_result = gpt_cache.get(combined_prompt)
        if cached_result:
            # Parse batch response
            batch_results = parse_batch_response(cached_result, len(batch))
            results.extend(batch_results)
        else:
            # Make API call
            try:
                response = gpt_function(combined_prompt)
                gpt_cache.set(combined_prompt, response)
                batch_results = parse_batch_response(response, len(batch))
                results.extend(batch_results)
            except Exception as e:
                print(f"Batch processing failed: {e}")
                # Fallback to individual calls
                for item in batch:
                    try:
                        result = gpt_function(item['prompt'])
                        results.append(result)
                    except Exception as e2:
                        results.append({"error": str(e2)})
        
        # Rate limiting
        time.sleep(1)
    
    return results

def parse_batch_response(response: str, expected_items: int) -> List[Dict]:
    """Parse batch response into individual results."""
    try:
        # Try JSON parsing first
        if response.strip().startswith('['):
            return json.loads(response)
    except:
        pass
    
    # Fallback: split by item markers
    results = []
    lines = response.split('\n')
    current_result = ""
    
    for line in lines:
        if line.startswith('Item ') and line[5].isdigit():
            if current_result:
                results.append({"result": current_result.strip()})
            current_result = ""
        else:
            current_result += line + "\n"
    
    if current_result:
        results.append({"result": current_result.strip()})
    
    # Pad if needed
    while len(results) < expected_items:
        results.append({"error": "No response"})
    
    return results[:expected_items] 