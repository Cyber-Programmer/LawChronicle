import asyncio
import os
from app.core.services.phase4_service import Phase4Service

async def test_actual_service_call():
    """Test calling the actual service method to see what happens"""
    
    # Initialize service
    phase4_service = Phase4Service()
    
    print("🔍 Testing actual service call...")
    
    # Call the actual method with minimal parameters
    progress_data = []
    
    try:
        async for progress in phase4_service.process_date_enrichment(
            processing_mode="single",
            selected_batch="batch_1",
            batch_size=50,
            dry_run=False,  # Let's try actual writing
            generate_metadata=True,
            collection_prefix="batch"
        ):
            progress_data.append(progress)
            print(f"Progress: {progress.get('status', 'unknown')} - {progress.get('documents_processed', 0)}/{progress.get('total_documents', 0)}")
            
            # Stop after getting a few progress updates to avoid long processing
            if len(progress_data) >= 10 or progress.get('status') == 'completed':
                print(f"Stopping - Status: {progress.get('status')}")
                break
    
    except Exception as e:
        print(f"❌ Error during processing: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\n📊 Progress data collected: {len(progress_data)} updates")
    for i, data in enumerate(progress_data):
        print(f"  {i+1}: {data.get('status')} - {data.get('documents_processed', 0)} docs")
    
    # Check if any target collections were created
    target_collections = await phase4_service.target_db.list_collection_names()
    print(f"\n🗃️ Target collections after processing: {target_collections}")
    
    # Check specific target collection
    target_name = "batch_1"
    if target_name in target_collections:
        count = await phase4_service.target_db[target_name].count_documents({})
        print(f"Documents in {target_name}: {count}")
    else:
        print(f"❌ Target collection {target_name} was not created!")

if __name__ == "__main__":
    asyncio.run(test_actual_service_call())
