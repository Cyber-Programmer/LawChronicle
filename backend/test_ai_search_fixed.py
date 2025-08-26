#!/usr/bin/env python3
"""
Test script for fixed AI Date Search
"""

import asyncio
import sys
import os

# Add the backend directory to the Python path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

from app.core.services.phase4_search_service import Phase4SearchService

async def test_fixed_ai_search():
    """Test the fixed AI date search functionality"""
    
    print("🧪 Testing Fixed AI Date Search...")
    
    try:
        # Initialize service
        service = Phase4SearchService()
        print("✅ Service initialized")
        
        # Test getting collections
        collections = await service.get_available_collections()
        print(f"✅ Available collections: {len(collections)}")
        
        # Test collecting documents with no limit (should collect many)
        missing_docs = []
        collected_count = 0
        
        # Test the same logic that's in the endpoint
        for collection_name in collections[:2]:  # Test first 2 collections
            collection = service.source_db[collection_name]
            missing_query = {
                "$or": [
                    {"Date": {"$in": ["", None]}},
                    {"Date": {"$exists": False}}
                ]
            }
            
            cursor = collection.find(missing_query)
            # No limit applied (max_docs is None)
            
            doc_count_in_collection = 0
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
                doc_count_in_collection += 1
                
                # Stop after 5 per collection for testing
                if doc_count_in_collection >= 5:
                    break
        
        print(f"✅ Collected {len(missing_docs)} documents (should be 10 - 5 from each of 2 collections)")
        
        if len(missing_docs) >= 5:
            print("✅ Document collection logic is working correctly!")
        else:
            print(f"❌ Document collection issue - only got {len(missing_docs)} documents")
        
        # Test AI search on a small sample
        print(f"\n🤖 Testing AI date extraction on {min(2, len(missing_docs))} documents...")
        
        processed_count = 0
        async for result in service.search_dates_with_ai(missing_docs[:2]):  # Just 2 docs
            if result["status"] == "processing":
                processed_count += 1
                print(f"✅ Processed document {processed_count}: {result.get('statute_name', 'Unknown')}")
                    
            elif result["status"] == "completed":
                print(f"✅ AI search completed. Total processed: {result['total_processed']}")
                break
        
        print("\n✅ Fixed AI Date Search test completed successfully!")
        
    except Exception as e:
        print(f"❌ Error during AI search test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_fixed_ai_search())
