import asyncio
import os
from app.core.services.phase4_service import Phase4Service

async def test_minimal_processing():
    """Test the exact processing logic with detailed logging"""
    
    # Initialize service
    phase4_service = Phase4Service()
    
    print("🔍 Testing minimal processing logic...")
    
    # Test processing mode and batch selection
    processing_mode = "single"
    selected_batch = "batch_1"
    
    print(f"Processing mode: {processing_mode}")
    print(f"Selected batch: {selected_batch}")
    
    # Determine which batches to process (exact same logic as service)
    if processing_mode == "single" and selected_batch:
        batches_to_process = [selected_batch]
    else:
        batches_to_process = await phase4_service.get_available_batches()
    
    print(f"Batches to process: {batches_to_process}")
    
    # Compute total documents across selected batches
    total_documents = 0
    for b in batches_to_process:
        count = await phase4_service.source_db[b].count_documents({})
        print(f"Documents in {b}: {count}")
        total_documents += count
    
    print(f"Total documents to process: {total_documents}")
    
    # Test the batch iteration
    processed_documents = 0
    completed_batches = []
    
    for batch_index, batch_name in enumerate(batches_to_process):
        print(f"\n🔄 Processing batch {batch_index + 1}/{len(batches_to_process)}: {batch_name}")
        
        batch_number = batch_name.split("_")[-1] if "_" in batch_name else str(batch_index + 1)
        target_collection_name = f"batch_{batch_number}"
        
        print(f"Target collection: {target_collection_name}")
        
        # Test the document cursor
        source_collection = phase4_service.source_db[batch_name]
        target_collection = phase4_service.target_db[target_collection_name]
        
        print("Creating cursor...")
        cursor = source_collection.find({})
        
        # Test iteration
        doc_count = 0
        async for document in cursor:
            doc_count += 1
            if doc_count <= 3:  # Only process first 3 docs for testing
                print(f"Processing document {doc_count}: {document.get('_id')}")
                
                # Test the enrichment
                try:
                    enriched_doc = await phase4_service._enrich_document_dates(document)
                    print(f"  - Enriched successfully")
                    
                    # Test writing (dry run)
                    print(f"  - Would write to {target_collection_name}")
                    processed_documents += 1
                    
                except Exception as e:
                    print(f"  - Error enriching: {e}")
            
            if doc_count >= 3:  # Stop after 3 for testing
                break
        
        print(f"Processed {doc_count} documents from {batch_name}")
        completed_batches.append(batch_name)
    
    print(f"\n✅ Test completed!")
    print(f"Total processed: {processed_documents}")
    print(f"Completed batches: {completed_batches}")

if __name__ == "__main__":
    asyncio.run(test_minimal_processing())
