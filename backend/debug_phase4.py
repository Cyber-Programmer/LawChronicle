#!/usr/bin/env python3
"""Debug script to test Phase 4 processing parameters"""

import asyncio
import os
import sys
from motor.motor_asyncio import AsyncIOMotorClient

async def debug_phase4():
    """Debug Phase 4 processing setup"""
    
    # Connect to the database
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    source_db = client["Batched-Statutes"]
    
    print("Phase 4 Processing Debug")
    print("=" * 40)
    
    # Check available batches
    collections = await source_db.list_collection_names()
    batches = [c for c in collections if c.startswith("batch")]
    print(f"Available batches: {batches}")
    
    # Count total documents
    total_docs = 0
    for batch in batches:
        try:
            count = await source_db[batch].count_documents({})
            print(f"  {batch}: {count} documents")
            total_docs += count
        except Exception as e:
            print(f"  {batch}: ERROR - {e}")
    
    print(f"Total documents across all batches: {total_docs}")
    
    # Test parameters that would be passed to _process_single_batch
    print("\nTesting parameters:")
    print(f"  batch_size (chunk_size): 100")
    print(f"  global_processed_count: 0")  
    print(f"  global_total_count: {total_docs}")
    print(f"  dry_run: True")
    
    # Test the comparison that was failing
    chunk_size = 100
    global_total_count = total_docs
    print(f"\nTesting comparisons:")
    print(f"  chunk_size >= 0: {chunk_size >= 0}")
    print(f"  global_total_count >= 0: {global_total_count >= 0}")
    print(f"  chunk_size type: {type(chunk_size)}")
    print(f"  global_total_count type: {type(global_total_count)}")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(debug_phase4())
