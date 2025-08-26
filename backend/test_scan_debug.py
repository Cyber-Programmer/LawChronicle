import asyncio
import os
import sys
sys.path.append(os.path.abspath('.'))

from app.core.services.phase4_search_service import Phase4SearchService

async def test_scan_operation():
    try:
        service = Phase4SearchService()
        
        print("Testing scan operation...")
        
        # Define a simple progress callback
        progress_updates = []
        async def progress_callback(data):
            progress_updates.append(data)
            print(f"Progress: {data}")
        
        # Test with a single collection
        collections = ['batch_2']  # We know this has missing dates
        
        print(f"Starting scan for collections: {collections}")
        results = await service.scan_missing_dates(
            collection_names=collections,
            progress_callback=progress_callback
        )
        
        print(f"Scan completed!")
        print(f"Progress updates received: {len(progress_updates)}")
        print(f"Results summary: {results['summary']}")
        
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_scan_operation())
