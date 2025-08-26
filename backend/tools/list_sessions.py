import asyncio
from app.core.services.phase4_search_service import Phase4SearchService

async def main(limit=10):
    svc = Phase4SearchService()
    await asyncio.sleep(0.5)
    collection = svc.search_db['search_sessions']
    cursor = collection.find({}).sort('created_at', -1).limit(limit)
    print('Recent sessions:')
    async for s in cursor:
        print('---')
        print('session_id:', s.get('session_id'))
        print('created_at:', s.get('created_at'))
        print('total_documents:', s.get('total_documents'))
        print('metadata:', s.get('metadata'))

if __name__ == '__main__':
    import sys
    lim = int(sys.argv[1]) if len(sys.argv)>1 else 10
    asyncio.run(main(lim))
