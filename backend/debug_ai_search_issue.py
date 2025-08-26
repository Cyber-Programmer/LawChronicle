#!/usr/bin/env python3
"""
Debug script to trace AI search issue
"""

import asyncio
import sys
import os

# Add the backend directory to the Python path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

from app.core.services.phase4_search_service import Phase4SearchService

async def debug_ai_search_issue():
    """Debug the specific AI search issue"""
    
    print("🔍 Debugging AI Search Issue...")
    
    try:
        # Initialize service
        service = Phase4SearchService()
        print("✅ Service initialized")
        
        # Create a sample document like the endpoint does
        collections = await service.get_available_collections()
        print(f"✅ Got {len(collections)} collections")
        
        # Simulate the exact same logic as the endpoint
        missing_docs = []
        collected_count = 0
        
        collection_name = collections[0]  # Test with first collection only
        collection = service.source_db[collection_name]
        missing_query = {
            "$or": [
                {"Date": {"$in": ["", None]}},
                {"Date": {"$exists": False}}
            ]
        }
        
        cursor = collection.find(missing_query)
        
        # Get just 2 documents for testing
        async for doc in cursor:
            missing_docs.append({
                "Collection": collection_name,
                "Document_ID": str(doc["_id"]),
                "Statute_Name": doc.get("Statute_Name", ""),
                "Province": doc.get("Province", ""),
                "Sections_Sample": " ".join([
                    section.get("Section_Text", "") 
                    for section in doc.get("Sections", [])[:3]
                ])[:2000]
            })
            collected_count += 1
            
            if collected_count >= 2:  # Just 2 for testing
                break
        
        print(f"✅ Collected {len(missing_docs)} documents for testing")
        
        if len(missing_docs) == 0:
            print("❌ No documents collected - this is the issue!")
            return
        
        # Debug the first document
        print(f"\n📄 First document details:")
        print(f"   - Statute Name: {missing_docs[0].get('Statute_Name')}")
        print(f"   - Collection: {missing_docs[0].get('Collection')}")
        print(f"   - Sections Sample Length: {len(missing_docs[0].get('Sections_Sample', ''))}")
        print(f"   - Document ID: {missing_docs[0].get('Document_ID')}")
        
        # Test AI search step by step
        print(f"\n🤖 Testing AI search step by step...")
        
        result_count = 0
        processing_count = 0
        error_count = 0
        
        async for result in service.search_dates_with_ai(missing_docs):
            result_count += 1
            print(f"\n📊 Result #{result_count}:")
            print(f"   Status: {result.get('status')}")
            
            if result["status"] == "processing":
                processing_count += 1
                print(f"   - Document: {result.get('statute_name')}")
                print(f"   - Extracted Date: {result.get('extracted_date')}")
                print(f"   - Confidence: {result.get('confidence')}")
                print(f"   - Progress: {result.get('progress')}%")
                
            elif result["status"] == "completed":
                print(f"   - Total Processed: {result.get('total_processed')}")
                print(f"   - Final Progress: {result.get('progress')}%")
                break
                
            elif result["status"] == "error":
                error_count += 1
                print(f"   - Error: {result.get('error')}")
                print(f"   - Document: {result.get('document_id')}")
        
        print(f"\n📈 Summary:")
        print(f"   - Total Results: {result_count}")
        print(f"   - Processing Results: {processing_count}")
        print(f"   - Error Results: {error_count}")
        
        if processing_count == 0:
            print("❌ Issue found: No processing results generated!")
        else:
            print("✅ AI search is working correctly")
        
    except Exception as e:
        print(f"❌ Error during debug: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_ai_search_issue())
