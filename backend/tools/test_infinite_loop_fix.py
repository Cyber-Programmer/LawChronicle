#!/usr/bin/env python3
"""
Test to verify infinite loop fix
"""

import asyncio
import aiohttp
import time
from datetime import datetime

async def test_api_stability():
    """Test that API endpoints respond consistently without hanging"""
    
    print("🔍 Testing API stability after infinite loop fix...")
    print(f"Time: {datetime.now()}")
    print()
    
    endpoints = [
        ("Status", "http://localhost:8000/api/v1/phase5/status"),
        ("Groups", "http://localhost:8000/api/v1/phase5/groups?page=1&limit=5"),
        ("Collections", "http://localhost:8000/api/v1/phase5/collections"),
        ("Provinces", "http://localhost:8000/api/v1/phase5/provinces"),
    ]
    
    async with aiohttp.ClientSession() as session:
        for i in range(3):  # Test 3 times
            print(f"--- Test Round {i+1} ---")
            
            for name, url in endpoints:
                start_time = time.time()
                try:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                        elapsed = time.time() - start_time
                        if response.status == 200:
                            data = await response.json()
                            print(f"✅ {name}: {response.status} ({elapsed:.2f}s)")
                        else:
                            print(f"❌ {name}: {response.status} ({elapsed:.2f}s)")
                except asyncio.TimeoutError:
                    elapsed = time.time() - start_time
                    print(f"⏰ {name}: TIMEOUT after {elapsed:.2f}s")
                except Exception as e:
                    elapsed = time.time() - start_time
                    print(f"💥 {name}: ERROR {str(e)[:50]} ({elapsed:.2f}s)")
            
            if i < 2:  # Don't wait after last iteration
                print("Waiting 2 seconds...")
                await asyncio.sleep(2)
            print()
    
    print("✅ API stability test completed!")
    print("If all requests completed quickly without timeouts, the infinite loop is fixed.")

if __name__ == "__main__":
    asyncio.run(test_api_stability())
