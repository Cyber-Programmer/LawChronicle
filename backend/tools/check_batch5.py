#!/usr/bin/env python3
"""
Check batch_5 for missing dates
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def check_batch5():
    """Check batch_5 specifically"""
    
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    db = client['Date-Enriched-Batches']
    collection = db['batch_5']
    
    print("🔧 Checking batch_5 for Missing Dates")
    print("=" * 50)
    
    total = await collection.count_documents({})
    print(f"📊 Total documents: {total}")
    
    # Count docs without dates
    missing_query = {
        "$or": [
            {"Date_Enacted": {"$exists": False}},
            {"Date_Enacted": None},
            {"Date_Enacted": ""}
        ]
    }
    
    missing = await collection.count_documents(missing_query)
    print(f"❌ Missing dates: {missing}")
    
    if missing > 0:
        print(f"\n📄 Sample document without date:")
        doc = await collection.find_one(missing_query)
        print(f"   📋 Statute: {doc.get('Statute_Name', 'Unknown')[:60]}...")
        
        sections = doc.get('Sections', [])
        print(f"   📊 Sections: {len(sections)}")
        
        if sections:
            section = sections[0]
            statute_text = section.get("Statute", "")
            section_text = section.get("Section_Text", "")
            combined = section.get("Statute", section.get("Section_Text", ""))
            
            print(f"   📋 Statute field: {len(statute_text)} chars")
            print(f"   📋 Section_Text field: {len(section_text)} chars")  
            print(f"   ✅ Combined: {len(combined)} chars")
            
            if combined:
                print(f"   📄 Preview: {combined[:100]}...")
                print("   ✅ Content available for AI processing!")
            else:
                print("   ❌ No text content available")
    else:
        print("\n✅ All documents in batch_5 already have dates!")
        print("   This explains why AI search completes immediately")
        
        # Check a sample document that has a date
        sample = await collection.find_one({})
        if sample:
            print(f"\n📄 Sample document WITH date:")
            print(f"   📋 Statute: {sample.get('Statute_Name', 'Unknown')[:60]}...")
            print(f"   📅 Date: {sample.get('Date_Enacted', 'None')}")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(check_batch5())
