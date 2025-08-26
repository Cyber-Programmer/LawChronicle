import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient

async def test_collections():
    try:
        client = AsyncIOMotorClient(os.getenv('MONGO_URI', 'mongodb://localhost:27017'))
        db = client.get_database('Date-Enriched-Batches')
        collections = await db.list_collection_names()
        print(f'Available collections: {collections}')
        
        for collection_name in collections[:3]:  # Test first 3 collections
            collection = db[collection_name]
            total_docs = await collection.count_documents({})
            missing_query = {
                "$or": [
                    {"Date": {"$in": ["", None]}},
                    {"Date": {"$exists": False}}
                ]
            }
            missing_docs = await collection.count_documents(missing_query)
            print(f'{collection_name}: {total_docs} total, {missing_docs} missing dates')
        
    except Exception as e:
        print(f'Error: {e}')

if __name__ == "__main__":
    asyncio.run(test_collections())
