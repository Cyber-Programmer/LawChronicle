#!/usr/bin/env python3
"""
Test frontend-backend integration for Phase 5 collection selection
"""

import requests
import json
from datetime import datetime

def test_collection_integration():
    base_url = "http://localhost:8000/api/v1/phase5"
    
    print("=== Testing Phase 5 Collection Integration ===")
    print(f"Time: {datetime.now()}")
    print()
    
    # Test 1: Get available collections
    print("1. Testing /collections endpoint")
    try:
        response = requests.get(f"{base_url}/collections")
        collections_data = response.json()
        print(f"   Collections: {collections_data}")
        print(f"   Available count: {len(collections_data.get('collections', []))}")
        print()
    except Exception as e:
        print(f"   ERROR: {e}")
        return
    
    # Test 2: Get status without collection (should default to first available)
    print("2. Testing status without collection parameter")
    try:
        response = requests.get(f"{base_url}/status")
        status_data = response.json()
        print(f"   Source Collection: {status_data.get('source_collection')}")
        print(f"   Total Documents: {status_data.get('total_source_documents')}")
        print(f"   Grouped Documents: {status_data.get('grouped_documents')}")
        print(f"   Available Collections: {status_data.get('available_collections_count')}")
        print(f"   Azure OpenAI: {status_data.get('azure_openai_configured')}")
        print()
    except Exception as e:
        print(f"   ERROR: {e}")
        return
    
    # Test 3: Test different collections
    test_collections = ['batch_1', 'batch_2', 'batch_3']
    for collection in test_collections:
        print(f"3.{test_collections.index(collection)+1}. Testing status with collection '{collection}'")
        try:
            response = requests.get(f"{base_url}/status?collection={collection}")
            status_data = response.json()
            print(f"   Source Collection: {status_data.get('source_collection')}")
            print(f"   Total Documents: {status_data.get('total_source_documents')}")
            print(f"   Grouped Documents: {status_data.get('grouped_documents')}")
            print(f"   Target Collection: {status_data.get('target_collection')}")
            print()
        except Exception as e:
            print(f"   ERROR: {e}")
    
    print("=== Integration Test Complete ===")
    print()
    print("Frontend should now show:")
    print("- Collection count: 10")
    print("- Correct statute count when collection changes")
    print("- Azure OpenAI: Configured")
    print("- Different grouped document counts per collection")

if __name__ == "__main__":
    test_collection_integration()
