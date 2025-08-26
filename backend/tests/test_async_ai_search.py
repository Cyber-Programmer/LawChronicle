#!/usr/bin/env python3
"""
Complete test of async AI search API with progress monitoring
"""

import requests
import json
import time

def test_async_ai_search():
    """Test the complete async AI search workflow"""
    
    base_url = "http://localhost:8000"
    
    print("🔧 Testing Async AI Search API")
    print("=" * 60)
    
    # Step 1: Start the search
    payload = {
        "collection_names": ["5batch"],
        "max_docs": 3,
        "output_format": "json"
    }
    
    print(f"📋 Starting search with: {payload}")
    
    try:
        # Start the search
        response = requests.post(
            f"{base_url}/api/v1/phase4/search/search-dates-ai",
            json=payload
        )
        
        if response.status_code != 200:
            print(f"❌ Failed to start search: {response.status_code}")
            print(response.text)
            return
        
        start_result = response.json()
        search_id = start_result.get('search_id')
        
        print(f"✅ Search started with ID: {search_id}")
        print()
        
        # Step 2: Monitor progress
        print("🔄 Monitoring progress...")
        completed = False
        max_checks = 30  # Max 30 checks (30 seconds)
        
        for i in range(max_checks):
            time.sleep(1)  # Wait 1 second between checks
            
            # Check progress
            progress_response = requests.get(
                f"{base_url}/api/v1/phase4/search/search-progress/{search_id}"
            )
            
            if progress_response.status_code == 200:
                progress = progress_response.json()
                status = progress.get('status', 'unknown')
                
                print(f"   📊 Check {i+1}: Status = {status}")
                
                if 'progress' in progress and isinstance(progress['progress'], dict):
                    prog_data = progress['progress']
                    collected = prog_data.get('documents_collected', 0)
                    processed = prog_data.get('documents_processed', 0)
                    print(f"      📋 Collected: {collected}, Processed: {processed}")
                elif 'documents_collected' in progress:
                    # Progress data is at root level
                    collected = progress.get('documents_collected', 0)
                    processed = progress.get('documents_processed', 0)
                    print(f"      📋 Collected: {collected}, Processed: {processed}")
                
                if status == 'completed':
                    completed = True
                    print("✅ Search completed!")
                    break
                elif status == 'failed':
                    print("❌ Search failed!")
                    print(f"   Error: {progress.get('error', 'Unknown error')}")
                    return
            else:
                print(f"   ⚠️ Progress check failed: {progress_response.status_code}")
        
        if not completed:
            print("⏰ Search timed out - still running after 30 seconds")
            return
        
        # Step 3: Get results
        print("\n📄 Fetching results...")
        results_response = requests.get(
            f"{base_url}/api/v1/phase4/search/search-results/{search_id}"
        )
        
        if results_response.status_code == 200:
            results = results_response.json()
            
            print("🎯 Final Results:")
            print(f"   📊 Total collected: {results.get('total_collected', 0)}")
            print(f"   ⚙️ Total processed: {results.get('total_processed', 0)}")
            print(f"   ✅ Dates found: {results.get('total_dates_found', 0)}")
            print(f"   ⏱️ Processing time: {results.get('processing_time', 0):.2f}s")
            
            # Show sample results
            if results.get('results') and len(results['results']) > 0:
                print("\n📄 Sample Results:")
                for i, doc in enumerate(results['results'][:2]):
                    print(f"\n   Document {i+1}:")
                    print(f"     📋 Statute: {doc.get('Statute_Name', 'N/A')[:60]}...")
                    print(f"     📅 Date: {doc.get('Extracted_Date', 'None')}")
                    print(f"     🎯 Confidence: {doc.get('Confidence', 'N/A')}")
                    print(f"     💭 Method: {doc.get('Method', 'N/A')}")
                
                # Check if we actually got meaningful results
                processed_count = results.get('total_processed', 0)
                if processed_count > 0:
                    print(f"\n✅ SUCCESS: Field fix worked! {processed_count} documents processed")
                else:
                    print(f"\n❌ ISSUE: Still no documents processed despite fix")
            else:
                print("\n❌ No results returned")
        else:
            print(f"❌ Failed to get results: {results_response.status_code}")
            print(results_response.text)
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    test_async_ai_search()
