"""
Debug runner to invoke run_ai_date_search directly for a quick local test.
"""
import asyncio
from app.api.v1.endpoints import phase4_search

async def main():
    # Run a short AI search with limited documents to exercise path
    await phase4_search.run_ai_date_search('debugsearch_0001', ['batch_1'], max_docs=3)

if __name__ == '__main__':
    asyncio.run(main())
