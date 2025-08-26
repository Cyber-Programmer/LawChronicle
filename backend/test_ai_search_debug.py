#!/usr/bin/env python3
"""
Test script for AI Date Search debugging
"""

import asyncio
import sys
import os

# Add the backend directory to the Python path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

from app.core.services.phase4_search_service import Phase4SearchService

async def test_ai_search():
    """Test the AI date search functionality"""
    
    print("🧪 Testing AI Date Search...")
    
    try:
        # Initialize service
        service = Phase4SearchService()
        print("✅ Service initialized")
        
        # Test getting collections
        collections = await service.get_available_collections()
        print(f"✅ Available collections: {len(collections)}")
        for i, col in enumerate(collections[:5]):  # Show first 5
            print(f"   {i+1}. {col}")
        
        # Test getting missing documents count
        missing_docs = []
        total_missing_count = 0
        
        for collection_name in collections[:2]:  # Test first 2 collections
            collection = service.source_db[collection_name]
            missing_query = {
                "$or": [
                    {"Date": {"$in": ["", None]}},
                    {"Date": {"$exists": False}}
                ]
            }
            count = await collection.count_documents(missing_query)
            total_missing_count += count
            print(f"✅ {collection_name}: {count} missing dates")
        
        print(f"✅ Total missing documents in first 2 collections: {total_missing_count}")
        
        # Test collecting a few documents for AI processing
        collected_count = 0
        for collection_name in collections[:1]:  # Test just first collection
            collection = service.source_db[collection_name]
            missing_query = {
                "$or": [
                    {"Date": {"$in": ["", None]}},
                    {"Date": {"$exists": False}}
                ]
            }
            
            cursor = collection.find(missing_query).limit(2)  # Just 2 docs for testing
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
                if collected_count >= 2:
                    break
            
            if collected_count >= 2:
                break
        
        print(f"✅ Collected {len(missing_docs)} documents for testing")
        
        # Test AI client
        if service.azure_client:
            print("✅ Azure OpenAI client is initialized")
        else:
            print("❌ Azure OpenAI client is NOT initialized")
            return
        
        # Test AI search on a small sample
        print("\n🤖 Testing AI date extraction on sample documents...")
        
        processed_count = 0
        async for result in service.search_dates_with_ai(missing_docs[:1]):  # Just 1 doc
            if result["status"] == "processing":
                processed_count += 1
                print(f"✅ Processed document {processed_count}: {result.get('statute_name', 'Unknown')}")
                if result.get("extracted_date"):
                    print(f"   📅 Found date: {result['extracted_date']} (confidence: {result.get('confidence', 0)})")
                else:
                    print(f"   ❌ No date found")
                    
            elif result["status"] == "completed":
                print(f"✅ AI search completed. Total processed: {result['total_processed']}")
                break
        
        print("\n✅ AI Date Search test completed successfully!")
        
    except Exception as e:
        print(f"❌ Error during AI search test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_ai_search())
