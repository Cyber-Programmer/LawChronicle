#!/usr/bin/env python3
"""
Find collections with missing Date_Enacted
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def find_missing():
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    db = client['Date-Enriched-Batches']
    
    collections = ['batch_1', 'batch_2', 'batch_3', 'batch_4', 'batch_5', 
                  'batch_6', 'batch_7', 'batch_8', 'batch_9', 'batch_10']
    
    print("🔍 Collections with Missing Date_Enacted:")
    print("=" * 50)
    
    for coll_name in collections:
        collection = db[coll_name]
        missing = await collection.count_documents({
            "$or": [
                {"Date_Enacted": {"$in": ["", None]}},
                {"Date_Enacted": {"$exists": False}}
            ]
        })
        if missing > 0:
            print(f"📋 {coll_name}: {missing} missing dates")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(find_missing())
