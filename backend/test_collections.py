import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def test_status():
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    target_db = client['Batched-Statutes']
    
    all_collections = await target_db.list_collection_names()
    print('Collections that start with "batch":')
    batch_collections = [name for name in all_collections if name.startswith('batch')]
    for name in sorted(batch_collections):
        count = await target_db[name].count_documents({})
        print(f'  {name}: {count} documents')
    
    print()
    print('Collections that start with "batch_":')
    batch_underscore = [name for name in all_collections if name.startswith('batch_')]
    for name in sorted(batch_underscore):
        count = await target_db[name].count_documents({})
        print(f'  {name}: {count} documents')

asyncio.run(test_status())
