#!/usr/bin/env python3
"""
Check which collections have missing dates
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def check_missing_dates():
    """Check missing dates across all collections"""
    
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    db = client['Date-Enriched-Batches']
    
    collections = ['1batch', '2batch', '3batch', '4batch', '5batch', 
                  '6batch', '7batch', '8batch', '9batch', '10batch']
    
    print("📊 Missing Dates Analysis")
    print("=" * 40)
    
    total_missing = 0
    collections_with_missing = []
    
    for coll_name in collections:
        try:
            collection = db[coll_name]
            
            # Count total docs
            total = await collection.count_documents({})
            
            # Count docs without dates
            missing_query = {
                "$or": [
                    {"Date_Enacted": {"$exists": False}},
                    {"Date_Enacted": None},
                    {"Date_Enacted": ""}
                ]
            }
            missing = await collection.count_documents(missing_query)
            
            print(f"{coll_name}: {missing}/{total} missing dates")
            
            if missing > 0:
                total_missing += missing
                collections_with_missing.append(coll_name)
        
        except Exception as e:
            print(f"{coll_name}: Error - {e}")
    
    print(f"\n🎯 Summary:")
    print(f"   Total collections with missing dates: {len(collections_with_missing)}")
    print(f"   Collections: {collections_with_missing}")
    print(f"   Total missing dates: {total_missing}")
    
    # Test one collection with missing dates
    if collections_with_missing:
        test_coll = collections_with_missing[0]
        print(f"\n🔧 Testing content from {test_coll}:")
        
        collection = db[test_coll]
        doc = await collection.find_one(missing_query)
        
        if doc:
            sections = doc.get("Sections", [])
            print(f"   📄 Document: {doc.get('Statute_Name', 'Unknown')[:50]}...")
            print(f"   📊 Sections: {len(sections)}")
            
            if sections:
                section = sections[0]
                statute = section.get("Statute", "")
                section_text = section.get("Section_Text", "")
                combined = section.get("Statute", section.get("Section_Text", ""))
                
                print(f"   📋 Statute field: {len(statute)} chars")
                print(f"   📋 Section_Text field: {len(section_text)} chars")
                print(f"   ✅ Combined (our fix): {len(combined)} chars")
                
                if combined:
                    print(f"   📄 Preview: {combined[:100]}...")
                    print("   ✅ SUCCESS: Content available after fix!")
                else:
                    print("   ❌ No content even after fix")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(check_missing_dates())
