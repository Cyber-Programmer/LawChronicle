import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def check_final_results():
    """Check the final processing results"""
    
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    target_db = client.get_database("Date-Enriched-Batches")
    
    print("🔍 Checking final processing results...")
    
    # List all collections
    collections = await target_db.list_collection_names()
    print(f"Target collections: {collections}")
    
    # Check each batch collection
    for collection_name in collections:
        if collection_name.startswith('batch_'):
            count = await target_db[collection_name].count_documents({})
            print(f"  {collection_name}: {count} documents")
            
            # Sample a document to verify the date merge worked
            sample = await target_db[collection_name].find_one({})
            if sample:
                print(f"    Sample document:")
                print(f"      Date: {sample.get('Date', 'NOT FOUND')}")
                print(f"      Promulgation_Date: {sample.get('Promulgation_Date', 'FIELD REMOVED (GOOD)')}")
                print(f"      date_metadata: {sample.get('date_metadata', {})}")
    
    await client.close()

if __name__ == "__main__":
    asyncio.run(check_final_results())
