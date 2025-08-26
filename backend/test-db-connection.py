import asyncio
from app.core.database import db, connect_to_mongo

async def test():
    await connect_to_mongo()
    print('Connected:', db.db is not None)

asyncio.run(test())
