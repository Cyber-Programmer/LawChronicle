import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.services.phase4_service import Phase4Service

async def test_batch_detection():
    """Test if batch detection and iteration works correctly"""
    
    # Initialize service (it creates its own client)
    phase4_service = Phase4Service()
    
    print("🔍 Testing batch detection...")
    
    # Test 1: Check if get_available_batches returns something
    available_batches = await phase4_service.get_available_batches()
    print(f"Available batches: {available_batches}")
    print(f"Number of batches found: {len(available_batches)}")
    
    if not available_batches:
        print("❌ No batches found! This explains why processing doesn't work.")
        return
    
    # Test 2: Check document count for first batch
    first_batch = available_batches[0]
    doc_count = await phase4_service.source_db[first_batch].count_documents({})
    print(f"Documents in {first_batch}: {doc_count}")
    
    # Test 3: Check if we can iterate documents
    print(f"🔍 Testing document iteration for {first_batch}...")
    cursor = phase4_service.source_db[first_batch].find({}).limit(2)
    docs_found = []
    async for doc in cursor:
        docs_found.append(doc.get('_id'))
    
    print(f"Sample document IDs: {docs_found}")
    
    # Test 4: Check target database connection
    target_collections = await phase4_service.target_db.list_collection_names()
    print(f"Target database collections: {target_collections}")
    
    print("✅ Batch detection and document iteration working correctly!")

if __name__ == "__main__":
    asyncio.run(test_batch_detection())
