#!/usr/bin/env python3
"""
Test the exact query from our fixed code
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def test_exact_query():
    """Test the exact query we're using in the API"""
    
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    db = client['Date-Enriched-Batches']
    collection = db['batch_5']
    
    print("🔧 Testing Exact Query from Fixed Code")
    print("=" * 50)
    
    # Test our exact query from the fixed code
    missing_query = {
        "$or": [
            {"Date_Enacted": {"$in": ["", None]}},
            {"Date_Enacted": {"$exists": False}}
        ]
    }
    
    print("📋 Query:")
    print(f"   {missing_query}")
    print()
    
    count = await collection.count_documents(missing_query)
    print(f"📊 Documents found: {count}")
    
    if count > 0:
        print(f"\n📄 Sample documents:")
        cursor = collection.find(missing_query).limit(3)
        i = 0
        async for doc in cursor:
            i += 1
            print(f"   Document {i}:")
            print(f"     📋 Statute: {doc.get('Statute_Name', 'Unknown')[:50]}...")
            print(f"     📅 Date_Enacted: {repr(doc.get('Date_Enacted', 'NOT_FOUND'))}")
            
            # Test sections
            sections = doc.get('Sections', [])
            if sections:
                section = sections[0]
                statute_text = section.get("Statute", "")
                combined = section.get("Statute", section.get("Section_Text", ""))
                print(f"     📝 Statute text: {len(statute_text)} chars")
                print(f"     ✅ Combined text: {len(combined)} chars")
        
        print(f"\n✅ Query is working - {count} documents available for AI processing")
    else:
        print("\n❌ Query found no documents")
        
        # Check what Date_Enacted values actually exist
        sample = await collection.find_one({})
        if sample:
            print(f"\n🔍 Sample document structure:")
            print(f"   Date_Enacted: {repr(sample.get('Date_Enacted', 'FIELD_NOT_FOUND'))}")
            print(f"   Available fields: {list(sample.keys())[:10]}...")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(test_exact_query())
