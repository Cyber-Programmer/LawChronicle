#!/usr/bin/env python3
"""Simple script to show the actual merge behavior on real data"""

import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient

async def demonstrate_merge_logic():
    """Show how the merge logic works with real data samples"""
    
    # Connect to the database
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    source_db = client["Batched-Statutes"]
    source_collection = source_db["batch_1"]
    
    print("Phase 4 Date Merge Logic Demonstration")
    print("=" * 50)
    
    # Get some sample documents with different date field combinations
    print("\n1. Documents with both Date and Promulgation_Date:")
    cursor = source_collection.find({
        "Date": {"$exists": True, "$ne": "", "$ne": None},
        "Promulgation_Date": {"$exists": True, "$ne": "", "$ne": None}
    }).limit(2)
    
    async for doc in cursor:
        print(f"   _id: {doc['_id']}")
        print(f"   Date: '{doc.get('Date', 'NOT_SET')}'")
        print(f"   Promulgation_Date: '{doc.get('Promulgation_Date', 'NOT_SET')}'")
        print(f"   → After merge: Date field will be '{doc.get('Date')}' (Date preferred)")
        print(f"   → Promulgation_Date will be removed")
        print()
    
    print("\n2. Documents with only Date field:")
    cursor = source_collection.find({
        "Date": {"$exists": True, "$ne": "", "$ne": None},
        "$or": [
            {"Promulgation_Date": {"$exists": False}},
            {"Promulgation_Date": {"$in": ["", None]}}
        ]
    }).limit(2)
    
    async for doc in cursor:
        print(f"   _id: {doc['_id']}")
        print(f"   Date: '{doc.get('Date', 'NOT_SET')}'")
        print(f"   Promulgation_Date: '{doc.get('Promulgation_Date', 'NOT_SET')}'")
        print(f"   → After merge: Date field will be '{doc.get('Date')}'")
        print(f"   → Promulgation_Date will be removed (if exists)")
        print()
    
    print("\n3. Documents with only Promulgation_Date field:")
    cursor = source_collection.find({
        "Promulgation_Date": {"$exists": True, "$ne": "", "$ne": None},
        "$or": [
            {"Date": {"$exists": False}},
            {"Date": {"$in": ["", None]}}
        ]
    }).limit(2)
    
    async for doc in cursor:
        print(f"   _id: {doc['_id']}")
        print(f"   Date: '{doc.get('Date', 'NOT_SET')}'")
        print(f"   Promulgation_Date: '{doc.get('Promulgation_Date', 'NOT_SET')}'")
        print(f"   → After merge: Date field will be '{doc.get('Promulgation_Date')}'")
        print(f"   → Promulgation_Date will be removed")
        print()
    
    print("\n4. Documents with neither or both empty:")
    cursor = source_collection.find({
        "$or": [
            {"Date": {"$in": ["", None]}, "Promulgation_Date": {"$in": ["", None]}},
            {"Date": {"$exists": False}, "Promulgation_Date": {"$exists": False}}
        ]
    }).limit(2)
    
    async for doc in cursor:
        print(f"   _id: {doc['_id']}")
        print(f"   Date: '{doc.get('Date', 'NOT_SET')}'")
        print(f"   Promulgation_Date: '{doc.get('Promulgation_Date', 'NOT_SET')}'")
        print(f"   → After merge: Date field will be '' (empty string)")
        print(f"   → Promulgation_Date will be removed (if exists)")
        print()
    
    # Get counts to understand the data distribution
    total_docs = await source_collection.count_documents({})
    both_filled = await source_collection.count_documents({
        "Date": {"$exists": True, "$ne": "", "$ne": None},
        "Promulgation_Date": {"$exists": True, "$ne": "", "$ne": None}
    })
    only_date = await source_collection.count_documents({
        "Date": {"$exists": True, "$ne": "", "$ne": None},
        "$or": [
            {"Promulgation_Date": {"$exists": False}},
            {"Promulgation_Date": {"$in": ["", None]}}
        ]
    })
    only_prom = await source_collection.count_documents({
        "Promulgation_Date": {"$exists": True, "$ne": "", "$ne": None},
        "$or": [
            {"Date": {"$exists": False}},
            {"Date": {"$in": ["", None]}}
        ]
    })
    
    print(f"\nData Distribution Summary:")
    print(f"Total documents: {total_docs}")
    print(f"Both Date and Promulgation_Date filled: {both_filled}")
    print(f"Only Date filled: {only_date}")
    print(f"Only Promulgation_Date filled: {only_prom}")
    print(f"Neither or both empty: {total_docs - both_filled - only_date - only_prom}")
    
    print(f"\nExpected processing result:")
    print(f"- All {total_docs} documents should be processed successfully")
    print(f"- {both_filled} documents will use Date field (Date preferred over Promulgation_Date)")
    print(f"- {only_date} documents will keep their Date field")
    print(f"- {only_prom} documents will move Promulgation_Date to Date field")
    print(f"- {total_docs - both_filled - only_date - only_prom} documents will have empty Date field")
    print(f"- All documents will have Promulgation_Date field removed")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(demonstrate_merge_logic())
