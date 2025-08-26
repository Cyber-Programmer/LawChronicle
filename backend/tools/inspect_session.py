import asyncio
import os
from app.core.services.phase4_search_service import Phase4SearchService

async def main(session_id):
    svc = Phase4SearchService()
    # Wait a moment to ensure DB client initialized
    await asyncio.sleep(0.5)
    try:
        info = await svc.get_session_info(session_id)
        print('SESSION INFO:')
        print(info)
        results = await svc.get_search_results(session_id)
        print('\nRESULTS LENGTH:', len(results))
        if len(results) > 0:
            print(results[:3])
    except Exception as e:
        print('ERROR:', e)

if __name__ == '__main__':
    import sys
    sid = sys.argv[1] if len(sys.argv) > 1 else '20250819_184425'
    asyncio.run(main(sid))
