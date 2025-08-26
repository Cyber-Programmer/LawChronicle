#!/usr/bin/env python3

import asyncio
import sys
import os

# Add the backend directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

async def test_ai_service_with_api_structure():
    """
    Test AI service with exact same structure the API uses
    """
    try:
        from backend.app.core.services.phase4_search_service import Phase4SearchService
        from motor.motor_asyncio import AsyncIOMotorClient
        
        # Get real data from the database like the API does
        client = AsyncIOMotorClient("mongodb://localhost:27017")
        db = client["Date-Enriched-Batches"]
        collection = db["batch_9"]
        
        # Find a document that needs date enrichment (like API does)
        missing_query = {
            "$or": [
                {"Date": {"$in": ["", None]}},
                {"Date": {"$exists": False}}
            ]
        }
        
        cursor = collection.find(missing_query).limit(2)
        
        # Build the exact document structure the API creates
        api_docs = []
        async for doc in cursor:
            api_doc = {
                "Collection": "batch_9",
                "Document_ID": str(doc["_id"]),
                "Statute_Name": doc.get("Statute_Name", ""),
                "Province": doc.get("Province", ""),
                "Sections_Sample": " ".join([
                    section.get("Statute", section.get("Section_Text", ""))  # Try both field names
                    for section in doc.get("Sections", [])[:3]
                ])[:2000]
            }
            api_docs.append(api_doc)
            
            print(f"📄 API Document Structure:")
            print(f"   Collection: {api_doc['Collection']}")
            print(f"   Document_ID: {api_doc['Document_ID']}")
            print(f"   Statute_Name: {api_doc['Statute_Name']}")
            print(f"   Sections_Sample length: {len(api_doc['Sections_Sample'])}")
            print(f"   Sections_Sample preview: {api_doc['Sections_Sample'][:150]}...")
            print()
        
        print(f"🔍 Testing AI service with {len(api_docs)} API-structured documents...")
        
        search_service = Phase4SearchService()
        
        result_count = 0
        async for result in search_service.search_dates_with_ai(api_docs):
            result_count += 1
            print(f"📡 Result {result_count}: {result}")
            
            if result["status"] == "completed":
                print(f"✅ AI Search completed!")
                print(f"   📈 Total processed: {result.get('total_processed', 'N/A')}")
                break
        
        await client.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_ai_service_with_api_structure())
