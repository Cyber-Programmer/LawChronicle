"""
Batch processing module for LawChronicle API
Handles large-scale document processing in configurable batches
"""

import asyncio
from typing import List, Dict, Any, Callable, Optional
from datetime import datetime
import logging
from ..core.config import settings

logger = logging.getLogger(__name__)

class BatchProcessor:
    """Handles batch processing of documents with configurable batch sizes and timeouts"""
    
    def __init__(self, 
                 max_batch_size: int = None,
                 batch_timeout: int = None):
        self.max_batch_size = max_batch_size or settings.max_batch_size
        self.batch_timeout = batch_timeout or settings.batch_timeout
        self.processing_history: List[Dict[str, Any]] = []
    
    async def process_in_batches(self, 
                                items: List[Any],
                                processor_func: Callable,
                                batch_name: str = None) -> Dict[str, Any]:
        """
        Process items in batches with progress tracking
        
        Args:
            items: List of items to process
            processor_func: Function to apply to each batch
            batch_name: Optional name for the batch operation
            
        Returns:
            Dictionary with processing results and statistics
        """
        if not batch_name:
            batch_name = f"batch_{datetime.now().strftime('%Y%m%d')}"
        
        total_items = len(items)
        total_batches = (total_items + self.max_batch_size - 1) // self.max_batch_size
        
        logger.info(f"Starting batch processing: {total_items} items in {total_batches} batches")
        
        results = {
            "batch_name": batch_name,
            "total_items": total_items,
            "total_batches": total_batches,
            "max_batch_size": self.max_batch_size,
            "start_time": datetime.now().isoformat(),
            "batches_processed": 0,
            "items_processed": 0,
            "errors": [],
            "success": True
        }
        
        try:
            for batch_num in range(total_batches):
                start_idx = batch_num * self.max_batch_size
                end_idx = min(start_idx + self.max_batch_size, total_items)
                batch_items = items[start_idx:end_idx]
                
                logger.info(f"Processing batch {batch_num + 1}/{total_batches} "
                          f"({len(batch_items)} items)")
                
                # Process batch with timeout
                try:
                    await asyncio.wait_for(
                        processor_func(batch_items, batch_num),
                        timeout=self.batch_timeout
                    )
                    
                    results["batches_processed"] += 1
                    results["items_processed"] += len(batch_items)
                    
                    logger.info(f"Batch {batch_num + 1} completed successfully")
                    
                except asyncio.TimeoutError:
                    error_msg = f"Batch {batch_num + 1} timed out after {self.batch_timeout}s"
                    logger.error(error_msg)
                    results["errors"].append(error_msg)
                    results["success"] = False
                    
                except Exception as e:
                    error_msg = f"Batch {batch_num + 1} failed: {str(e)}"
                    logger.error(error_msg)
                    results["errors"].append(error_msg)
                    results["success"] = False
                
                # Add small delay between batches to prevent overwhelming the system
                await asyncio.sleep(0.1)
        
        except Exception as e:
            error_msg = f"Batch processing failed: {str(e)}"
            logger.error(error_msg)
            results["errors"].append(error_msg)
            results["success"] = False
        
        finally:
            results["end_time"] = datetime.now().isoformat()
            results["duration_seconds"] = (
                datetime.fromisoformat(results["end_time"]) - 
                datetime.fromisoformat(results["start_time"])
            ).total_seconds()
            
            # Log to processing history
            self.processing_history.append(results)
            
            logger.info(f"Batch processing completed: {results['items_processed']}/{total_items} "
                      f"items processed in {results['duration_seconds']:.2f}s")
        
        return results
    
    def get_processing_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent processing history"""
        return self.processing_history[-limit:] if self.processing_history else []
    
    def get_batch_status(self, batch_name: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific batch by name"""
        for batch in reversed(self.processing_history):
            if batch.get("batch_name") == batch_name:
                return batch
        return None

# Example usage functions
async def process_documents_batch(documents: List[Dict[str, Any]], batch_num: int) -> Dict[str, Any]:
    """Example document processing function"""
    # Simulate processing time
    await asyncio.sleep(0.5)
    
    processed_count = 0
    for doc in documents:
        # Example processing logic
        if "content" in doc:
            doc["processed"] = True
            doc["batch_number"] = batch_num
            processed_count += 1
    
    return {
        "batch_number": batch_num,
        "documents_processed": processed_count,
        "status": "completed"
    }

async def normalize_statutes_batch(statutes: List[Dict[str, Any]], batch_num: int) -> Dict[str, Any]:
    """Example statute normalization function"""
    # Simulate processing time
    await asyncio.sleep(0.3)
    
    normalized_count = 0
    for statute in statutes:
        if "name" in statute:
            # Example normalization logic
            statute["normalized_name"] = statute["name"].strip().title()
            statute["batch_number"] = batch_num
            normalized_count += 1
    
    return {
        "batch_number": batch_num,
        "statutes_normalized": normalized_count,
        "status": "completed"
    }
