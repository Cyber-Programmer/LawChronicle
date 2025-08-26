#!/usr/bin/env python3
"""Debug script to test database connectivity and writing"""

import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime

async def test_database_write():
    """Test if we can write to the target database"""
    
    print("Testing Phase 4 Database Write")
    print("=" * 40)
    
    # Connect to databases
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    source_db = client["Batched-Statutes"]
    target_db = client["Date-Enriched-Batches"]
    
    # Test 1: Check if we can connect and list collections
    try:
        source_collections = await source_db.list_collection_names()
        target_collections = await target_db.list_collection_names()
        print(f"✅ Database connection successful")
        print(f"   Source DB collections: {len(source_collections)}")
        print(f"   Target DB collections: {len(target_collections)}")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return
    
    # Test 2: Try to read a sample document from source
    try:
        sample_doc = await source_db["batch_1"].find_one()
        if sample_doc:
            print(f"✅ Can read from source database")
            print(f"   Sample document ID: {sample_doc['_id']}")
            print(f"   Date field: {sample_doc.get('Date', 'NOT_SET')}")
            print(f"   Promulgation_Date field: {sample_doc.get('Promulgation_Date', 'NOT_SET')}")
        else:
            print("❌ No documents found in batch_1")
            return
    except Exception as e:
        print(f"❌ Failed to read from source: {e}")
        return
    
    # Test 3: Try to write a test document to target
    test_doc = {
        "_id": "test_write_" + datetime.now().strftime("%Y%m%d_%H%M%S"),
        "Date": "01-Jan-2025",
        "Test": True,
        "date_metadata": {
            "extraction_method": "test",
            "processing_timestamp": datetime.utcnow().isoformat()
        }
    }
    
    try:
        result = await target_db["test_batch"].insert_one(test_doc)
        print(f"✅ Successfully wrote test document")
        print(f"   Inserted ID: {result.inserted_id}")
        
        # Verify it was written
        retrieved = await target_db["test_batch"].find_one({"_id": test_doc["_id"]})
        if retrieved:
            print(f"✅ Test document verified in target database")
        else:
            print(f"❌ Test document not found after writing")
            
    except Exception as e:
        print(f"❌ Failed to write to target database: {e}")
        return
    
    # Test 4: Check permissions by attempting to create/drop a collection
    try:
        test_collection = target_db["permission_test"]
        await test_collection.insert_one({"test": "permission"})
        await test_collection.drop()
        print(f"✅ Database write permissions confirmed")
    except Exception as e:
        print(f"❌ Database permission issue: {e}")
        
    # Test 5: Clean up test document
    try:
        await target_db["test_batch"].delete_one({"_id": test_doc["_id"]})
        print(f"✅ Cleanup completed")
    except Exception as e:
        print(f"⚠️ Cleanup failed: {e}")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(test_database_write())
