#!/usr/bin/env python3
"""
Simple script to monitor API calls from frontend
"""

import time
from collections import defaultdict
import requests
import threading

# Monitor API calls over time
def monitor_api_calls():
    call_counts = defaultdict(int)
    start_time = time.time()
    
    print("Monitoring API calls... (press Ctrl+C to stop)")
    print("Note: If the frontend has infinite loops, you'll see constant API calls")
    
    try:
        while True:
            current_time = time.time()
            elapsed = current_time - start_time
            
            # Check various endpoints
            endpoints = [
                '/api/v1/phase5/status',
                '/api/v1/phase5/groups?page=1&limit=20',
                '/api/v1/phase5/provinces',
                '/api/v1/phase5/collections'
            ]
            
            for endpoint in endpoints:
                try:
                    response = requests.get(f'http://localhost:8000{endpoint}', timeout=1)
                    if response.status_code == 200:
                        call_counts[endpoint] += 1
                except:
                    pass  # Ignore errors for monitoring
            
            # Print stats every 5 seconds
            if int(elapsed) % 5 == 0 and elapsed > 0:
                print(f"\n--- Stats after {int(elapsed)} seconds ---")
                for endpoint, count in call_counts.items():
                    rate = count / elapsed * 60  # calls per minute
                    print(f"{endpoint}: {count} calls ({rate:.1f}/min)")
                
                # Check for suspicious activity
                if any(rate > 60 for rate in [count / elapsed * 60 for count in call_counts.values()]):
                    print("⚠️  WARNING: High API call rate detected - possible infinite loop!")
                else:
                    print("✅ API call rate looks normal")
            
            time.sleep(1)
            
    except KeyboardInterrupt:
        print(f"\n\nMonitoring stopped after {elapsed:.1f} seconds")
        print("Final call counts:")
        for endpoint, count in call_counts.items():
            rate = count / elapsed * 60
            print(f"  {endpoint}: {count} calls ({rate:.1f}/min)")

if __name__ == "__main__":
    monitor_api_calls()
