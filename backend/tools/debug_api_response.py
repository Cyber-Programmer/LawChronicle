#!/usr/bin/env python3
"""
Debug the AI search API response to see what's happening
"""

import requests
import json

def debug_ai_search_api():
    """Debug AI search through the FastAPI endpoint"""
    
    base_url = "http://localhost:8000"
    
    print("🔧 Debugging AI Search API Response")
    print("=" * 60)
    
    # Test single collection with limited documents
    payload = {
        "collection_names": ["5batch"],
        "max_docs": 3,
        "output_format": "json"  # Change to JSON to see the actual response
    }
    
    print(f"📋 Testing with: {payload}")
    print()
    
    try:
        print("🚀 Starting AI search...")
        response = requests.post(
            f"{base_url}/api/v1/phase4/search/search-dates-ai",
            json=payload,
            timeout=120
        )
        
        print(f"📊 Response Status: {response.status_code}")
        print(f"📊 Response Headers: {dict(response.headers)}")
        print()
        
        if response.status_code == 200:
            if response.headers.get('content-type', '').startswith('application/json'):
                # JSON response
                result = response.json()
                print("📄 JSON Response:")
                print(json.dumps(result, indent=2))
                
                # Check key metrics
                total_collected = result.get('total_collected', 0)
                total_processed = result.get('total_processed', 0)
                total_found = result.get('total_dates_found', 0)
                
                print(f"\n🎯 Key Metrics:")
                print(f"   📊 Collected: {total_collected}")
                print(f"   ⚙️ Processed: {total_processed}")
                print(f"   ✅ Found: {total_found}")
                
                if total_processed > 0:
                    print("✅ SUCCESS: Documents are being processed!")
                else:
                    print("❌ ISSUE: No documents were processed")
                    
            else:
                # Not JSON, might be Excel or other format
                print(f"📄 Response Content (first 200 chars):")
                print(response.content[:200])
        else:
            print(f"❌ Request failed with status {response.status_code}")
            try:
                error_detail = response.json()
                print(json.dumps(error_detail, indent=2))
            except:
                print(response.text)
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to backend")
    except requests.exceptions.Timeout:
        print("⏰ Request timed out")
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    debug_ai_search_api()
