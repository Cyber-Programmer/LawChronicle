import asyncio
from app.core.services.phase4_service import Phase4Service

async def test_frontend_parameters():
    """Test with the exact parameters the frontend is sending"""
    
    # Initialize service
    phase4_service = Phase4Service()
    
    print("🔍 Testing with frontend parameters...")
    print("Frontend defaults:")
    print("  processing_mode: 'all'")
    print("  selected_batch: '' (empty)")
    print("  batch_size: 100")
    print("  dry_run: False")
    print("  generate_metadata: True")
    print("  collection_prefix: 'batch'")
    
    # Test 1: Frontend parameters (all mode)
    print("\n=== TEST 1: Frontend 'all' mode ===")
    progress_data = []
    
    try:
        async for progress in phase4_service.process_date_enrichment(
            processing_mode="all",        # Frontend default
            selected_batch="",            # Frontend sends empty string
            batch_size=100,               # Frontend default
            dry_run=False,                # Frontend setting
            generate_metadata=True,       # Frontend default
            collection_prefix="batch"     # Frontend default
        ):
            progress_data.append(progress)
            print(f"Progress: {progress.get('status', 'unknown')} - {progress.get('documents_processed', 0)}/{progress.get('total_documents', 0)}")
            
            # Stop after getting a few progress updates
            if len(progress_data) >= 3:
                break
    
    except Exception as e:
        print(f"❌ Error during processing: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\n📊 Progress data collected: {len(progress_data)} updates")
    
    # Test 2: Working parameters (single mode)
    print("\n=== TEST 2: Working 'single' mode ===")
    progress_data2 = []
    
    try:
        async for progress in phase4_service.process_date_enrichment(
            processing_mode="single",     # What worked
            selected_batch="batch_1",     # What worked
            batch_size=50,                # What worked
            dry_run=False,
            generate_metadata=True,
            collection_prefix="batch"
        ):
            progress_data2.append(progress)
            print(f"Progress: {progress.get('status', 'unknown')} - {progress.get('documents_processed', 0)}/{progress.get('total_documents', 0)}")
            
            # Stop after getting a few progress updates
            if len(progress_data2) >= 3:
                break
    
    except Exception as e:
        print(f"❌ Error during processing: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\n📊 Progress data collected: {len(progress_data2)} updates")
    
    # Check target collections
    target_collections = await phase4_service.target_db.list_collection_names()
    print(f"\n🗃️ Target collections after both tests: {target_collections}")

if __name__ == "__main__":
    asyncio.run(test_frontend_parameters())
