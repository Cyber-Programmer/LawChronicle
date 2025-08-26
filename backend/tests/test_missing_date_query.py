#!/usr/bin/env python3

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import sys
import os

# Add the backend directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

async def test_missing_date_query():
    """
    Test the corrected missing date query to see if we find documents without dates
    """
    try:
        # Connect to MongoDB
        client = AsyncIOMotorClient("mongodb://localhost:27017")
        db = client["Date-Enriched-Batches"]
        
        # Test the missing date query with corrected field name
        missing_query = {
            "$or": [
                {"Date": {"$in": ["", None]}},
                {"Date": {"$exists": False}}
            ]
        }
        
        print("🔍 Testing missing date query with field 'Date'...")
        
        # Check each collection
        collections = ["batch_1", "batch_2", "batch_3", "batch_4", "batch_5", 
                      "batch_6", "batch_7", "batch_8", "batch_9", "batch_10"]
        
        total_missing = 0
        for collection_name in collections:
            try:
                collection = db[collection_name]
                count = await collection.count_documents(missing_query)
                total_missing += count
                print(f"📊 {collection_name}: {count} documents missing Date field")
                
                if count > 0:
                    # Get a sample document
                    sample = await collection.find_one(missing_query)
                    if sample:
                        print(f"   📝 Sample document ID: {sample.get('_id')}")
                        print(f"   📝 Has Date field: {'Date' in sample}")
                        print(f"   📝 Date value: {sample.get('Date', 'NOT_PRESENT')}")
                        print()
                        
            except Exception as e:
                print(f"❌ Error checking {collection_name}: {e}")
        
        print(f"📈 Total documents missing Date field: {total_missing}")
        
        # Also test: documents with empty/null dates
        empty_date_query = {"Date": {"$in": ["", None]}}
        print(f"\n🔍 Testing for documents with empty/null Date values...")
        
        total_empty = 0
        for collection_name in collections:
            try:
                collection = db[collection_name]
                count = await collection.count_documents(empty_date_query)
                total_empty += count
                if count > 0:
                    print(f"📊 {collection_name}: {count} documents with empty Date")
                    
            except Exception as e:
                print(f"❌ Error checking {collection_name}: {e}")
        
        print(f"📈 Total documents with empty Date: {total_empty}")
        
        # Test: documents that DO have dates
        has_date_query = {
            "Date": {"$exists": True, "$nin": ["", None]}
        }
        print(f"\n🔍 Testing for documents that DO have Date values...")
        
        total_with_dates = 0
        for collection_name in collections:
            try:
                collection = db[collection_name]
                count = await collection.count_documents(has_date_query)
                total_with_dates += count
                print(f"📊 {collection_name}: {count} documents WITH Date")
                
                if count > 0:
                    # Get a sample document with date
                    sample = await collection.find_one(has_date_query)
                    if sample:
                        print(f"   📝 Sample with date: {sample.get('Date')}")
                        
            except Exception as e:
                print(f"❌ Error checking {collection_name}: {e}")
        
        print(f"📈 Total documents WITH Date: {total_with_dates}")
        
        await client.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_missing_date_query())
