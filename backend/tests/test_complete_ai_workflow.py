#!/usr/bin/env python3

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import sys
import os

# Add the backend directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from backend.app.core.services.phase4_search_service import Phase4SearchService

async def test_complete_ai_workflow():
    """
    Test the complete AI workflow with corrected field names
    """
    try:
        # Initialize the service
        search_service = Phase4SearchService()
        
        print("🔍 Testing complete AI workflow with corrected fields...")
        
        # Test with a small batch first
        collections = ["batch_9"]  # The document you showed is from batch_9
        
        print(f"📊 Testing AI search on collections: {collections}")
        
        # Get a sample document that needs date enrichment
        client = AsyncIOMotorClient("mongodb://localhost:27017")
        db = client["Date-Enriched-Batches"]
        collection = db["batch_9"]
        
        # Find a document that needs date enrichment
        missing_query = {
            "$or": [
                {"Date": {"$in": ["", None]}},
                {"Date": {"$exists": False}}
            ]
        }
        
        sample_doc = await collection.find_one(missing_query)
        if sample_doc:
            print(f"📝 Found sample document: {sample_doc['_id']}")
            print(f"📝 Statute Name: {sample_doc.get('Statute_Name', 'N/A')}")
            print(f"📝 Current Date: '{sample_doc.get('Date', 'EMPTY')}'")
            
            # Test AI extraction on this specific document
            if "Sections" in sample_doc and sample_doc["Sections"]:
                section = sample_doc["Sections"][0]
                statute_text = section.get("Statute", section.get("Section_Text", ""))
                
                if statute_text:
                    print(f"📝 Text length: {len(statute_text)} characters")
                    print(f"📝 Text preview: {statute_text[:200]}...")
                    
                    # Test AI extraction
                    print(f"\n🤖 Testing AI date extraction...")
                    result = await search_service._extract_date_with_ai(statute_text)
                    
                    if result:
                        print(f"✅ AI Result: {result}")
                        print(f"   📅 Date: {result.get('date', 'N/A')}")
                        print(f"   🎯 Confidence: {result.get('confidence', 'N/A')}")
                        print(f"   📋 Method: {result.get('method', 'N/A')}")
                        print(f"   💭 Reasoning: {result.get('reasoning', 'N/A')}")
                    else:
                        print("❌ AI extraction returned None")
                else:
                    print("❌ No text content found in Statute field")
            else:
                print("❌ No sections found in document")
        else:
            print("❌ No documents found that need date enrichment")
        
        print(f"\n📊 Running search_dates_with_ai on {collections}...")
        
        # Call the main AI search function
        result = await search_service.search_dates_with_ai(
            collections=collections,
            limit=5  # Test with just 5 documents
        )
        
        print(f"✅ AI Search completed!")
        print(f"📈 Results: {result}")
        
        await client.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_complete_ai_workflow())
