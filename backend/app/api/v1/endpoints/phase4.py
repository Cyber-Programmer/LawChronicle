from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import Dict, Any, Optional, List
import json
import asyncio
from datetime import datetime
import os

from ....core.services.phase4_service import Phase4Service

router = APIRouter()
phase4_service = Phase4Service()

# Global processing state for SSE
processing_state = {
    "is_processing": False,
    "progress": None,
    "error": None
}

@router.get("/status")
async def get_status():
    """Get Phase 4 processing status and available batches."""
    print(f"[DEBUG] Phase 4 status endpoint called WITHOUT auth requirement")
    try:
        status_data = await phase4_service.get_status()
        available_batches = await phase4_service.get_available_batches()

        return {
            "success": True,
            "current_phase": "Phase 4: Enhanced Date Processing",
            "status": "ready",
            "available_batches": available_batches,
            "database_info": {
                "source_db": getattr(phase4_service.source_db, 'name', 'Batched-Statutes'),
                "target_db": getattr(phase4_service.target_db, 'name', 'Date-Enriched-Batches'),
                "collections_count": len(available_batches)
            },
            **status_data
        }
    except Exception as e:
        print(f"[ERROR] Phase 4 status error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")

@router.get("/available-batches")
async def get_available_batches(db_name: Optional[str] = None):
    """Get list of available batch collections for processing.

    Optional query param `db_name` lets the caller list batches from another database.
    """
    try:
        batches = await phase4_service.get_available_batches(db_name)
        return {"success": True, "batches": batches}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get available batches: {str(e)}")


@router.post("/set-dbs")
async def set_phase4_databases(payload: Dict[str, str]):
    """Set source and/or target database names for Phase 4 processing on the running service.

    Body: { "source_db": "Batched-Statutes", "target_db": "Date-Enriched-Batches" }
    """
    try:
        source_db_name = payload.get("source_db")
        target_db_name = payload.get("target_db")
        if source_db_name:
            phase4_service.source_db = phase4_service.client[source_db_name]
        if target_db_name:
            phase4_service.target_db = phase4_service.client[target_db_name]

        return {"success": True, "message": "Phase 4 databases updated", "source_db": getattr(phase4_service.source_db, 'name', None), "target_db": getattr(phase4_service.target_db, 'name', None)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/start-processing")
async def start_processing(
    request_data: Dict[str, Any],
    background_tasks: BackgroundTasks
):
    """Start the date processing workflow."""
    try:
        if processing_state["is_processing"]:
            raise HTTPException(status_code=409, detail="Processing already in progress")
        processing_mode = request_data.get("processing_mode", "all")
        selected_batch = request_data.get("selected_batch")
        collection_prefix = request_data.get("collection_prefix", "batch")
        batch_size = request_data.get("batch_size", 50)  # Default to 50 if not provided
        dry_run = request_data.get("dry_run", False)
        # source_collection is deprecated/ignored in current implementation
        generate_metadata = request_data.get("generate_metadata", False)

        # Validate input
        if processing_mode == "single" and not selected_batch:
            raise HTTPException(status_code=400, detail="Selected batch required for single mode")

        # Reset processing state
        processing_state["is_processing"] = True
        processing_state["progress"] = None
        processing_state["error"] = None

        # Start background processing (updated parameter order)
        background_tasks.add_task(
            run_date_processing,
            processing_mode,
            selected_batch,
            collection_prefix,
            dry_run,
            batch_size,
            generate_metadata,
        )

        return {
            "success": True,
            "message": "Date processing started",
            "processing_mode": processing_mode,
            "collection_prefix": collection_prefix,
        }

    except Exception as e:
        processing_state["is_processing"] = False
        raise HTTPException(status_code=500, detail=f"Failed to start processing: {str(e)}")

@router.post("/stop-processing")
async def stop_processing():
    """Stop the current processing operation."""
    try:
        await phase4_service.stop_processing()
        processing_state["is_processing"] = False
        processing_state["progress"] = None
        
        return {
            "success": True,
            "message": "Processing stopped"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop processing: {str(e)}")

@router.get("/processing-progress")
async def get_processing_progress():
    """Server-Sent Events endpoint for real-time progress updates."""
    async def event_stream():
        while True:
            if processing_state["error"]:
                yield f"data: {json.dumps({'status': 'error', 'error': processing_state['error']})}\n\n"
                break
            elif not processing_state["is_processing"]:
                # Send final completion message regardless of whether there's progress data
                if processing_state["progress"]:
                    final_progress = processing_state["progress"].copy()
                    final_progress["status"] = "completed"
                    yield f"data: {json.dumps(final_progress)}\n\n"
                else:
                    # Send generic completion message if no progress data available
                    yield f"data: {json.dumps({'status': 'completed', 'message': 'Processing completed successfully'})}\n\n"
                break
            elif processing_state["progress"]:
                yield f"data: {json.dumps(processing_state['progress'])}\n\n"
            
            await asyncio.sleep(1)  # Update every second
    
    return StreamingResponse(
        event_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream"
        }
    )

@router.get("/export-results")
async def export_results():
    """Export processed results to Excel file."""
    try:
        excel_data = await phase4_service.export_results_to_excel()
        
        def iter_excel():
            yield excel_data
        
        # Use unified naming convention: {operation}-{database}-{collection}-{date}.xlsx
        date_str = datetime.now().strftime('%Y-%m-%d')
        filename = f"export-date-processed-results-{date_str}.xlsx"
        headers = {
            "Content-Disposition": f"attachment; filename={filename}"
        }
        
        return StreamingResponse(
            iter_excel(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers=headers
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export results: {str(e)}")


@router.get("/test-gpt")
async def test_gpt():
    """Quick health check for Azure OpenAI client (if configured)."""
    try:
        if not phase4_service.ai_enabled:
            return {"success": False, "message": "Azure OpenAI not configured"}

        # small test prompt
        prompt = "Return JSON: { \"ping\": \"pong\" }"
        resp = await phase4_service._call_azure_openai(prompt)
        if resp:
            return {"success": True, "message": "GPT responded", "response": resp}
        else:
            return {"success": False, "message": "No response from GPT"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.get("/metadata")
async def list_metadata(batch: Optional[str] = None):
    """List metadata files in the metadata folder and optionally fetch DB metadata documents for a given batch."""
    try:
        metadata_dir = os.path.join(os.path.dirname(__file__), '../../metadata')
        files = []
        if os.path.exists(metadata_dir):
            for fname in sorted(os.listdir(metadata_dir), reverse=True):
                if not fname.endswith('.json'):
                    continue
                if batch and batch not in fname:
                    continue
                path = os.path.join(metadata_dir, fname)
                try:
                    stat = os.stat(path)
                    files.append({
                        "filename": fname,
                        "path": path,
                        "size": stat.st_size,
                        "modified": stat.st_mtime
                    })
                except Exception:
                    continue

        # Also fetch DB metadata entries (if any)
        db_docs = []
        try:
            cursor = phase4_service.target_db["phase4_metadata"].find({})
            async for doc in cursor:
                doc["_id"] = str(doc.get("_id"))
                db_docs.append(doc)
        except Exception:
            # ignore DB access errors but return files if present
            pass

        return {"success": True, "files": files, "db_entries": db_docs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def run_date_processing(
    processing_mode: str,
    selected_batch: Optional[str],
    collection_prefix: str,
    dry_run: bool,
    batch_size: int = 50,  # Default parameter after non-default parameters
    generate_metadata: bool = False,
):
    """Background task for running the date processing workflow."""
    try:
        async for progress_update in phase4_service.process_date_enrichment(
            processing_mode=processing_mode,
            selected_batch=selected_batch,
            collection_prefix=collection_prefix,
            batch_size=batch_size,
            dry_run=dry_run,
            generate_metadata=generate_metadata,
        ):
            processing_state["progress"] = progress_update

    except Exception as e:
        processing_state["error"] = str(e)
        print(f"[ERROR] Date processing failed: {str(e)}")
    finally:
        processing_state["is_processing"] = False
        # Keep the last progress for the completion message
        print(f"[INFO] Date processing completed. Final state: {processing_state}")
