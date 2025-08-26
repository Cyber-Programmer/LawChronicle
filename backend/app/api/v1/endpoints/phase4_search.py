"""
Phase 4 Date Search API Endpoints

Provides endpoints for searching missing dates, AI-powered date extraction,
and managing the review workflow for date insertion.
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, File, Depends, Request
from bson import ObjectId
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel, Field
import pandas as pd
import io
from io import BytesIO, StringIO
import motor.motor_asyncio as motor_asyncio

from app.core.services.phase4_search_service import Phase4SearchService
from app.core.auth import get_current_user_with_roles, optional_current_user

router = APIRouter()
search_service = Phase4SearchService()

# Store for SSE clients
sse_clients: Dict[str, asyncio.Queue] = {}

# Request/Response Models
class ScanRequest(BaseModel):
    collections: Optional[List[str]] = None

class SearchRequest(BaseModel):
    collections: Optional[List[str]] = None
    use_ai: bool = True
    max_documents: Optional[int] = None  # None means process all missing dates

class ReviewRequest(BaseModel):
    session_id: str
    approved_dates: List[Dict[str, Any]]

class ScanResponse(BaseModel):
    scan_id: str
    collections_scanned: List[str]
    summary: Dict[str, Any]
    collection_breakdown: Dict[str, Any]
    sample_missing: List[Dict[str, Any]]

# Progress tracking
search_progress: Dict[str, Dict[str, Any]] = {}


async def sse_progress_callback(search_id: str, data: Dict[str, Any]):
    """Send progress updates via SSE"""
    print(f"[DEBUG] SSE callback for {search_id}, clients: {list(sse_clients.keys())}")
    if search_id in sse_clients:
        try:
            await sse_clients[search_id].put(data)
            print(f"[DEBUG] Progress sent to {search_id}: {data}")
        except Exception as e:
            print(f"[ERROR] SSE callback failed: {e}")
    else:
        print(f"[WARNING] No SSE client found for {search_id}")


@router.get("/collections")
async def get_available_collections():
    """Get list of available date-enriched collections"""
    try:
        collections = await search_service.get_available_collections()
        return {
            "status": "success",
            "collections": collections,
            "total_collections": len(collections)
        }
    except Exception as e:
        print(f"[ERROR] Get collections failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scan-missing-dates")
async def scan_missing_dates(request: ScanRequest, background_tasks: BackgroundTasks):
    """Scan for documents with missing dates"""
    try:
        scan_id = f"scan_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        print(f"[DEBUG] Scan endpoint called with scan_id: {scan_id}, collections: {request.collections}")
        
        # Start background scan
        background_tasks.add_task(
            run_missing_dates_scan,
            scan_id,
            request.collections
        )
        
        print(f"[DEBUG] Background task added for scan_id: {scan_id}")
        return {
            "status": "started",
            "scan_id": scan_id,
            "message": "Missing dates scan started"
        }
    except Exception as e:
        print(f"[ERROR] Start scan failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def run_missing_dates_scan(scan_id: str, collections: List[str] = None):
    """Background task to run missing dates scan"""
    try:
        print(f"[DEBUG] Starting scan {scan_id} for collections: {collections}")
        search_progress[scan_id] = {"status": "scanning", "progress": 0}
        
        async def progress_callback(data):
            print(f"[DEBUG] Progress callback for {scan_id}: {data}")
            search_progress[scan_id].update(data)
            await sse_progress_callback(scan_id, {
                "type": "scan_progress",
                "scan_id": scan_id,
                **data
            })
        
        # Run the scan
        print(f"[DEBUG] Starting actual scan operation...")
        results = await search_service.scan_missing_dates(
            collection_names=collections,
            progress_callback=progress_callback
        )
        
        print(f"[DEBUG] Scan completed with results: {results['summary']}")
        # Update progress with results
        search_progress[scan_id] = {
            "status": "completed",
            "progress": 100,
            "results": results
        }
        
        # Send completion notification
        await sse_progress_callback(scan_id, {
            "type": "scan_completed",
            "scan_id": scan_id,
            "results": results
        })
        
    except Exception as e:
        print(f"[ERROR] Background scan failed: {e}")
        search_progress[scan_id] = {
            "status": "error",
            "error": str(e)
        }
        await sse_progress_callback(scan_id, {
            "type": "scan_error",
            "scan_id": scan_id,
            "error": str(e)
        })


@router.get("/scan-progress/{scan_id}")
async def get_scan_progress(scan_id: str):
    """Get progress of a scan operation"""
    try:
        if scan_id not in search_progress:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        return {
            "status": "success",
            "scan_id": scan_id,
            **search_progress[scan_id]
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Get scan progress failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export-missing-dates")
async def export_missing_dates(request: ScanRequest):
    """Export documents with missing dates to Excel"""
    try:
        excel_data = await search_service.export_missing_dates_to_excel(
            collection_names=request.collections
        )
        # Use unified naming convention with PKT local date
        database_name = "date-enriched-batches"  # From the source database
        collections_str = "-".join(request.collections) if request.collections else "all"
        from zoneinfo import ZoneInfo
        pkt = ZoneInfo('Asia/Karachi')
        date_str = datetime.now(pkt).strftime('%Y-%m-%d')
        filename = f"search-missing-dates-{database_name}-{collections_str}-{date_str}.xlsx"

        return Response(
            excel_data,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        print(f"[ERROR] Export missing dates failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search-dates-ai")
async def search_dates_with_ai(request: SearchRequest, background_tasks: BackgroundTasks):
    """Start AI-powered date search for missing dates"""
    try:
        search_id = f"search_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        # Start background search
        background_tasks.add_task(
            run_ai_date_search,
            search_id,
            request.collections,
            request.max_documents
        )
        
        return {
            "status": "started",
            "search_id": search_id,
            "message": "AI date search started"
        }
    except Exception as e:
        print(f"[ERROR] Start AI search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def run_ai_date_search(search_id: str, collections: List[str] = None, max_docs: int = None):
    """Background task to run AI date search on all missing dates"""
    try:
        search_progress[search_id] = {"status": "searching", "progress": 0, "results": []}
        
        print(f"[DEBUG] run_ai_date_search called with search_id={search_id}, collections={collections}, max_docs={max_docs}")
        
        # First get missing documents
        if not collections:
            collections = await search_service.get_available_collections()
            print(f"[DEBUG] No collections specified, using all: {collections}")
        else:
            print(f"[DEBUG] Using specified collections: {collections}")
        
        # Get ALL missing documents for AI processing (like reference implementation)
        missing_docs = []
        total_missing_count = 0
        
        print(f"[DEBUG] Starting document collection...")
        
        # First, count total missing documents across all collections
        for collection_name in collections:
            collection = search_service.source_db[collection_name]
            missing_query = {
                "$or": [
                    {"Date": {"$in": ["", None]}},
                    {"Date": {"$exists": False}}
                ]
            }
            count = await collection.count_documents(missing_query)
            total_missing_count += count
            print(f"[DEBUG] {collection_name}: {count} missing documents")
        
        print(f"[DEBUG] Total missing documents to process: {total_missing_count}")
        
        # If max_docs is specified, limit the processing
        if max_docs is not None:
            total_missing_count = min(total_missing_count, max_docs)
            print(f"[DEBUG] Limited to {max_docs} documents for processing")
        
        # Collect documents for processing
        collected_count = 0
        for collection_name in collections:
            if max_docs and collected_count >= max_docs:
                break
                
            collection = search_service.source_db[collection_name]
            missing_query = {
                "$or": [
                    {"Date": {"$in": ["", None]}},
                    {"Date": {"$exists": False}}
                ]
            }
            
            cursor = collection.find(missing_query)
            
            # Apply limit only if max_docs is specified and we haven't exceeded it
            if max_docs:
                remaining_docs = max_docs - collected_count
                if remaining_docs > 0:
                    cursor = cursor.limit(remaining_docs)
                else:
                    break  # No more docs needed
            
            async for doc in cursor:
                missing_docs.append({
                    "Collection": collection_name,
                    "Document_ID": str(doc["_id"]),
                    "Statute_Name": doc.get("Statute_Name", ""),
                    "Province": doc.get("Province", ""),
                    "Sections_Sample": " ".join([
                        section.get("Statute", section.get("Section_Text", ""))  # Try both field names
                        for section in doc.get("Sections", [])[:3]
                    ])[:2000]
                })
                collected_count += 1
                
                if max_docs and collected_count >= max_docs:
                    break
        
        print(f"[DEBUG] Collected {len(missing_docs)} documents for AI processing")
        
        if len(missing_docs) == 0:
            print("[DEBUG] No documents to process - completing immediately")
            # Derive a session_id safely from the search_id when possible.
            parts = search_id.split('_')
            if len(parts) >= 3:
                session_id = f"{parts[1]}_{parts[2]}"
            elif len(parts) == 2:
                session_id = parts[1]
            else:
                session_id = search_id

            search_progress[search_id] = {
                "status": "completed",
                "progress": 100,
                "session_id": session_id,
                "total_processed": 0,
                "results": []
            }
            return
        
        print(f"[DEBUG] Starting AI search service with {len(missing_docs)} documents")
        
        results = []
        async for result in search_service.search_dates_with_ai(missing_docs):
            # Debug: log each yielded result from AI service
            print(f"[DEBUG] AI yielded result: {result}")

            if result["status"] == "processing":
                results.append(result)
                search_progress[search_id]["results"] = results
                search_progress[search_id]["progress"] = result["progress"]
                
                # Send progress update
                await sse_progress_callback(search_id, {
                    "type": "search_progress",
                    "search_id": search_id,
                    "progress": result["progress"],
                    "current_statute": result.get("statute_name", ""),
                    "processed_count": len(results)
                })
            
            elif result["status"] == "completed":
                # Debug: completed reached, log counts before saving
                print(f"[DEBUG] AI search completed, processed reported: {result.get('total_processed')}, collected results count: {len(results)}")

                # Save results and complete
                session_id = await search_service.save_search_results(results)
                print(f"[DEBUG] save_search_results returned session_id: {session_id}")

                search_progress[search_id] = {
                    "status": "completed",
                    "progress": 100,
                    "session_id": session_id,
                    "total_processed": result["total_processed"],
                    "results": results
                }
                
                await sse_progress_callback(search_id, {
                    "type": "search_completed",
                    "search_id": search_id,
                    "session_id": session_id,
                    "total_processed": result["total_processed"]
                })
                break
            
            elif result["status"] == "error":
                # Handle individual document errors but continue
                await sse_progress_callback(search_id, {
                    "type": "search_error",
                    "search_id": search_id,
                    "document_error": result
                })
        
    except Exception as e:
        print(f"[ERROR] AI search failed: {e}")
        search_progress[search_id] = {
            "status": "error",
            "error": str(e)
        }
        await sse_progress_callback(search_id, {
            "type": "search_error",
            "search_id": search_id,
            "error": str(e)
        })


@router.get("/search-progress/{search_id}")
async def get_search_progress(search_id: str):
    """Get progress of AI search operation"""
    try:
        if search_id not in search_progress:
            raise HTTPException(status_code=404, detail="Search not found")
        
        return {
            "status": "success",
            "search_id": search_id,
            **search_progress[search_id]
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Get search progress failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search-sessions")
async def get_search_sessions():
    """Get list of search sessions for review"""
    try:
        sessions = await search_service.get_search_sessions()
        return {
            "status": "success",
            "sessions": sessions
        }
    except Exception as e:
        print(f"[ERROR] Get search sessions failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/test-sse/{operation_id}")
async def test_sse(operation_id: str):
    """Test SSE endpoint for debugging"""
    print(f"[DEBUG] Test SSE endpoint called for {operation_id}")
    async def event_generator():
        for i in range(5):
            print(f"[DEBUG] Sending test message {i} for {operation_id}")
            yield f"data: {json.dumps({'type': 'test', 'message': f'Test message {i}', 'operation_id': operation_id})}\n\n"
            await asyncio.sleep(1)
        yield f"data: {json.dumps({'type': 'test_complete', 'operation_id': operation_id})}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/plain")


@router.get("/progress-stream/{operation_id}")
async def progress_stream(operation_id: str):
    """SSE endpoint for real-time progress updates"""
    print(f"[DEBUG] SSE client connecting for operation: {operation_id}")
    async def event_generator():
        # Create a queue for this client
        queue = asyncio.Queue()
        sse_clients[operation_id] = queue
        print(f"[DEBUG] SSE client registered for {operation_id}")
        
        try:
            # Send initial connection message
            yield f"data: {json.dumps({'type': 'connected', 'operation_id': operation_id})}\n\n"
            
            # Send existing progress if available
            if operation_id in search_progress:
                print(f"[DEBUG] Sending existing progress for {operation_id}: {search_progress[operation_id]}")
                yield f"data: {json.dumps({'type': 'status', **search_progress[operation_id]})}\n\n"
            
            # Stream updates
            while True:
                try:
                    # Wait for new data with timeout
                    data = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(data)}\n\n"
                    
                    # Check if operation is complete
                    if data.get("type") in ["scan_completed", "search_completed", "scan_error", "search_error"]:
                        break
                        
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield f"data: {json.dumps({'type': 'keepalive'})}\n\n"
                    
        except Exception as e:
            print(f"[ERROR] SSE stream error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            # Clean up
            if operation_id in sse_clients:
                del sse_clients[operation_id]
    
    return StreamingResponse(
        event_generator(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream"
        }
    )


@router.post("/stop-operation/{operation_id}")
async def stop_operation(operation_id: str):
    """Stop a running search or scan operation"""
    try:
        await search_service.stop_processing()
        
        # Update progress
        if operation_id in search_progress:
            search_progress[operation_id]["status"] = "stopped"
        
        # Notify via SSE
        await sse_progress_callback(operation_id, {
            "type": "operation_stopped",
            "operation_id": operation_id
        })
        
        return {
            "status": "success",
            "message": "Operation stopped"
        }
    except Exception as e:
        print(f"[ERROR] Stop operation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload-reviewed-excel")
async def upload_reviewed_excel(file: UploadFile = File(...), session_id: Optional[str] = None, current_user: dict = Depends(optional_current_user)):
    """Upload reviewed Excel file with approved dates"""
    try:
        if not file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(status_code=400, detail="Only Excel files are allowed")
        
        # Read Excel file
        content = await file.read()
        df = pd.read_excel(BytesIO(content), sheet_name="Missing_Dates")
        
        # Read sheet if not already a DataFrame (some callers may pass binary)
        try:
            # If df is not a DataFrame yet, ensure it's loaded (we already read content into df above)
            pass
        except Exception:
            pass

        # Filter approved dates
        approved_mask = df["Review_Status"].astype(str).str.lower() == "approved"
        approved_dates = df[approved_mask].to_dict("records")

        # If session_id provided, attach metadata to session (mark pending_review) and store binary in GridFS
        if session_id:
            stored_file_id = None
            try:
                # Save binary to GridFS bucket 'reviewed_files'
                try:
                    bucket = motor_asyncio.AsyncIOMotorGridFSBucket(search_service.search_db, bucket_name="reviewed_files")
                    stored_oid = await bucket.upload_from_stream(file.filename, io.BytesIO(content))
                    stored_file_id = str(stored_oid)
                except Exception as e:
                    # If GridFS saving fails, log and continue (preview still returned)
                    print(f"[WARNING] Failed to save reviewed file to GridFS for session {session_id}: {e}")

                coll = search_service.search_db["search_sessions"]
                meta = {
                    "filename": file.filename,
                    "uploaded_by": (current_user.get("user_id") if current_user else None) or (current_user.get("sub") if current_user else None),
                    "uploaded_at_utc": datetime.utcnow(),
                    "uploaded_at_local": datetime.now().astimezone().isoformat(),
                }
                if stored_file_id:
                    meta["file_id"] = stored_file_id

                await coll.update_one({"session_id": session_id}, {"$set": {
                    "status": "pending_review",
                    "reviewed_file_meta": meta,
                    "approved_rows_count": int(approved_mask.sum())
                }})
            except Exception as e:
                print(f"[WARNING] Failed to attach reviewed file to session {session_id}: {e}")

        return {
            "status": "success",
            "total_documents": len(df),
            "approved_dates": len(approved_dates),
            "approved_data": approved_dates[:5],  # Sample for preview
            "message": f"Found {len(approved_dates)} approved dates ready for insertion",
            "session_id": session_id
        }
    except Exception as e:
        print(f"[ERROR] Upload reviewed Excel failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/apply-approved-dates")
async def apply_approved_dates(request: Request, file: Optional[UploadFile] = File(None), session_id: Optional[str] = None, current_user: dict = Depends(get_current_user_with_roles)):
    """Apply approved dates from an uploaded reviewed Excel directly into the source DB.

    The uploaded workbook should contain a sheet named `Missing_Dates` (or similar).
    Rows with `Review_Status` == 'approved' (case-insensitive) will be applied.
    If a row lacks a `Collection` column, the endpoint will try to infer it from the
    uploaded filename (e.g., 'batch_1' in the filename).
    """
    try:
        # Accept session_id from JSON body for clients that send it in the request body
        try:
            if not session_id:
                body = await request.json()
                if isinstance(body, dict):
                    session_id = body.get('session_id') or session_id
        except Exception:
            # Not a JSON body or empty body - ignore
            pass

        # Either a file is provided or session_id refers to an existing reviewed file
        content = None
        if file:
            if not file.filename.endswith(('.xlsx', '.xls')):
                raise HTTPException(status_code=400, detail="Only Excel files are allowed")
            content = await file.read()
            stored_filename = file.filename
        elif session_id:
            # Try to read the reviewed file binary stored in GridFS via session metadata
            session_doc = await search_service.search_db["search_sessions"].find_one({"session_id": session_id})
            if not session_doc:
                raise HTTPException(status_code=404, detail="Session not found")
            file_id_str = session_doc.get("reviewed_file_meta", {}).get("file_id")
            if not file_id_str:
                raise HTTPException(status_code=400, detail="No reviewed file stored for session; please re-upload")
            try:
                bucket = motor_asyncio.AsyncIOMotorGridFSBucket(search_service.search_db, bucket_name="reviewed_files")
                grid_out = await bucket.open_download_stream(ObjectId(file_id_str))
                # read bytes
                try:
                    content = await grid_out.read()
                except AttributeError:
                    # fallback if grid_out behaves differently
                    content = b''
                stored_filename = session_doc.get("reviewed_file_meta", {}).get("filename")
            except Exception as e:
                print(f"[ERROR] Failed to read reviewed file from GridFS for session {session_id}: {e}")
                raise HTTPException(status_code=500, detail="Failed to retrieve stored reviewed file")
        else:
            raise HTTPException(status_code=400, detail="Either file or session_id required")

        # Load the Excel sheet into a DataFrame (primary sheet 'Missing_Dates' or fallback to first)
        try:
            df = pd.read_excel(BytesIO(content), sheet_name="Missing_Dates")
        except Exception:
            x = pd.ExcelFile(BytesIO(content))
            sheet_name = x.sheet_names[0]
            df = pd.read_excel(BytesIO(content), sheet_name=sheet_name)

        # Normalize header names (simple canonicalization)
        df.columns = [c.strip().replace(' ', '_') if isinstance(c, str) else c for c in df.columns]

        # Determine approved rows
        if 'Review_Status' not in df.columns:
            raise HTTPException(status_code=400, detail="Missing 'Review_Status' column in uploaded sheet")

        approved_mask = df['Review_Status'].astype(str).str.lower() == 'approved'
        approved_rows = df[approved_mask].to_dict('records')

        if not approved_rows:
            return {"status": "success", "message": "No approved rows found", "applied": 0}

        applied = 0
        failed = []

        # Infer collection from filename if needed
        import re
        # filename may come from uploaded file or from stored_filename (when using session_id)
        fname = (file.filename if file else (stored_filename if 'stored_filename' in locals() else '')) or ''
        m = re.search(r'(batch_\d+)', fname)
        inferred_collection = m.group(1) if m else None

        # Enforce role check: require 'admin' or 'reviewer' in token roles
        roles = current_user.get('roles') or current_user.get('role') or []
        if isinstance(roles, str):
            roles = [roles]
        allowed = any(r.lower() in ('admin', 'reviewer') for r in roles)
        if not allowed:
            raise HTTPException(status_code=403, detail="Insufficient permissions to apply approved dates")

        for row in approved_rows:
            # Try common column names
            collection = row.get('Collection') or row.get('collection') or row.get('Collection_Name') or inferred_collection
            document_id = row.get('Document_ID') or row.get('Document Id') or row.get('DocumentId') or row.get('DocumentId')
            approved_date = row.get('Approved_Date') or row.get('AI_Extracted_Date') or row.get('Extracted_Date') or row.get('Extracted Date')
            confidence = row.get('Confidence_Score') or row.get('Confidence')

            if not collection or not document_id or not approved_date:
                failed.append({"row": row, "reason": "missing collection/document_id/or date"})
                continue

            # Convert document id to ObjectId when possible
            try:
                oid = ObjectId(str(document_id))
            except Exception:
                # If not a valid ObjectId, try to update by string id field
                oid = None

            try:
                coll = search_service.source_db[collection]
                update_doc = {
                    'Date': search_service._normalize_date(str(approved_date)),
                    'Date_Confidence': confidence,
                    'Date_Extraction_Method': row.get('method') or row.get('Method') or 'manual_upload',
                    'Date_Reviewer': 'uploaded_excel',
                }

                if oid:
                    res = await coll.update_one({'_id': oid}, {'$set': update_doc})
                else:
                    # fallback: try match by string _id field
                    res = await coll.update_one({'_id': document_id}, {'$set': update_doc})

                if res.modified_count > 0:
                    applied += 1
                else:
                    failed.append({"row": row, "reason": "no document updated (not found or unchanged)"})

            except Exception as e:
                failed.append({"row": row, "reason": str(e)})

        return {
            "status": "success",
            "applied": applied,
            "failed_count": len(failed),
            "failed": failed[:10]
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Apply approved dates failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search-results/{session_id}")
async def get_search_results(session_id: str):
    """Get detailed results for a specific search session as Excel file"""
    try:
        results = await search_service.get_search_results(session_id)
        
        # Convert to DataFrame for Excel export
        if not results:
            raise HTTPException(status_code=404, detail="No results found for this session")
        
        df = pd.DataFrame(results)
        
        # Reorder columns for better readability
        column_order = [
            'statute_name', 'extracted_date', 'confidence', 'province', 
            'collection', 'document_id', 'extraction_source', 'sections_sample'
        ]
        
        # Only include columns that exist in the data
        available_columns = [col for col in column_order if col in df.columns]
        df = df[available_columns]
        
        # Rename columns for better readability
        df.columns = [col.replace('_', ' ').title() for col in df.columns]
        
        # Create Excel file in memory
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='AI_Search_Results', index=False)
            
            # Auto-adjust column widths
            worksheet = writer.sheets['AI_Search_Results']
            for column in worksheet.columns:
                max_length = 0
                column = [cell for cell in column]
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column[0].column_letter].width = adjusted_width
        
        output.seek(0)
        # Generate filename with unified naming convention using PKT
        # Get session info to determine which collections were processed
        session_info = await search_service.get_session_info(session_id)
        collections_processed = session_info.get("metadata", {}).get("source_collections", [])

        from zoneinfo import ZoneInfo
        pkt = ZoneInfo('Asia/Karachi')
        timestamp = datetime.now(pkt).strftime('%Y%m%d_%H%M%S')
        database_name = "date-enriched-batches"

        # Create collections string for filename
        if len(collections_processed) == 1:
            collections_str = collections_processed[0]
        elif len(collections_processed) <= 3:
            collections_str = "-".join(collections_processed)
        else:
            collections_str = "all-collections"

        filename = f"search-results-ai-extracted-dates-{database_name}-{collections_str}-{timestamp}.xlsx"

        return StreamingResponse(
            BytesIO(output.getvalue()),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Get search results failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/search-sessions")
async def clear_search_sessions():
    """Clear all search session history"""
    try:
        cleared_count = await search_service.clear_search_sessions()
        return {
            "status": "success",
            "message": f"Cleared {cleared_count} search sessions",
            "cleared_sessions": cleared_count
        }
    except Exception as e:
        print(f"[ERROR] Clear search sessions failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/search-sessions/{session_id}")
async def delete_search_session(session_id: str):
    """Delete a specific search session"""
    try:
        success = await search_service.delete_search_session(session_id)
        if success:
            return {
                "status": "success",
                "message": f"Search session {session_id} deleted",
                "session_id": session_id
            }
        else:
            raise HTTPException(status_code=404, detail="Search session not found")
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Delete search session failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
