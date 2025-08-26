#!/usr/bin/env python3
"""
Test if documents are being collected with our fixes
by testing the collection logic directly
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def test_collection_logic():
    """Test the exact collection logic from the fixed API"""
    
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    db = client['Date-Enriched-Batches']
    
    print("🔧 Testing Document Collection Logic After Fixes")
    print("=" * 60)
    
    collections = ["batch_5"]
    max_docs = 5
    
    missing_docs = []
    collected_count = 0
    
    for collection_name in collections:
        if max_docs and collected_count >= max_docs:
            break
            
        collection = db[collection_name]
        
        # Use our FIXED query
        missing_query = {
            "$or": [
                {"Date_Enacted": {"$in": ["", None]}},
                {"Date_Enacted": {"$exists": False}}
            ]
        }
        
        print(f"📋 Querying {collection_name} with: {missing_query}")
        
        cursor = collection.find(missing_query)
        
        # Apply limit like in the API
        if max_docs:
            remaining_docs = max_docs - collected_count
            if remaining_docs > 0:
                cursor = cursor.limit(remaining_docs)
            else:
                break
        
        print(f"🔍 Processing documents...")
        
        async for doc in cursor:
            # Use our FIXED section processing
            sections_sample = " ".join([
                section.get("Statute", section.get("Section_Text", ""))  # Our fix
                for section in doc.get("Sections", [])[:3]
            ])[:2000]
            
            missing_docs.append({
                "Collection": collection_name,
                "Document_ID": str(doc["_id"]),
                "Statute_Name": doc.get("Statute_Name", ""),
                "Province": doc.get("Province", ""),
                "Sections_Sample": sections_sample
            })
            collected_count += 1
            
            print(f"   📄 Doc {collected_count}: {doc.get('Statute_Name', 'Unknown')[:50]}...")
            print(f"      📝 Sample length: {len(sections_sample)} chars")
            print(f"      📅 Date_Enacted: {repr(doc.get('Date_Enacted', 'NOT_FOUND'))}")
            
            if max_docs and collected_count >= max_docs:
                break
    
    print(f"\n🎯 Collection Results:")
    print(f"   📊 Total collected: {len(missing_docs)}")
    print(f"   📋 Expected: {max_docs}")
    
    if len(missing_docs) > 0:
        print(f"   ✅ SUCCESS: Documents collected successfully")
        print(f"   📄 Sample document structure:")
        sample = missing_docs[0]
        for key, value in sample.items():
            if key == "Sections_Sample":
                print(f"      {key}: {len(str(value))} chars - '{str(value)[:100]}...'")
            else:
                print(f"      {key}: {value}")
    else:
        print(f"   ❌ ISSUE: No documents collected")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(test_collection_logic())
