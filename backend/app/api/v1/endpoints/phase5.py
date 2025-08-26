from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from fastapi.responses import StreamingResponse
from typing import Dict, Any, Optional, List
import json
import asyncio
import logging
from datetime import datetime
import os

from ....core.services.phase5_service import Phase5Service
from shared.types.common import (
    BaseResponse,
    Phase5Config,
    Phase5StartRequest,
    Phase5StartResponse,
    Phase5PreviewResponse
)

router = APIRouter()
phase5_service = Phase5Service()
logger = logging.getLogger(__name__)

# Global processing state for SSE
processing_state = {
    "is_processing": False,
    "progress": None,
    "error": None,
    "task_id": None
}

@router.get("/status")
async def get_status(
    collection: Optional[str] = Query(default=None, description="Specific collection to get status for")
):
    """Get Phase 5 processing status and configuration."""
    try:
        status_data = await phase5_service.get_status(collection=collection)
        
        # Get available collections count
        collections = await phase5_service.get_available_collections()
        status_data["available_collections_count"] = len(collections)
        
        # Return status directly to match frontend expectations
        return {
            "current_phase": "Phase 5: Contextual Statute Grouping & Versioning",
            "status": "ready" if not processing_state["is_processing"] else "processing",
            "is_processing": processing_state["is_processing"],
            "current_progress": processing_state.get("progress", 0),
            **status_data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")

@router.post("/start-grouping")
async def start_grouping(
    background_tasks: BackgroundTasks,
    request: Optional[Phase5StartRequest] = None
):
    """Start Phase 5 contextual statute grouping and versioning."""
    try:
        if processing_state["is_processing"]:
            raise HTTPException(status_code=409, detail="Phase 5 is already processing")
        
        # Use provided config or defaults
        config = request.config if request and request.config else Phase5Config()
        
        logger.info(f"Starting Phase 5 with config: {config.dict()}")
        
        # Start background task
        processing_state["is_processing"] = True
        processing_state["error"] = None
        background_tasks.add_task(run_grouping_task, config)
        
        return BaseResponse(
            success=True,
            message="Phase 5 contextual grouping started successfully",
            data={
                "started": True,
                "config_used": config.dict()
            }
        )
        
    except Exception as e:
        processing_state["is_processing"] = False
        logger.error(f"Failed to start Phase 5: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def run_grouping_task(config: Phase5Config):
    """Background task to run the grouping process."""
    try:
        processing_state["is_processing"] = True
        processing_state["error"] = None
        
        async for progress in phase5_service.group_and_version_statutes(config):
            processing_state["progress"] = progress
            
            if progress.get("status") == "completed":
                processing_state["is_processing"] = False
                logger.info("Phase 5 completed successfully")
                break
            elif progress.get("status") == "error":
                processing_state["is_processing"] = False
                processing_state["error"] = progress.get("error")
                logger.error(f"Phase 5 failed: {progress.get('error')}")
                break
                
    except Exception as e:
        processing_state["is_processing"] = False
        processing_state["error"] = str(e)
        logger.error(f"Phase 5 task failed: {e}")

@router.get("/progress-stream")
async def progress_stream():
    """Server-Sent Events stream for real-time progress updates."""
    
    async def event_generator():
        try:
            while True:
                if processing_state["progress"]:
                    yield f"data: {json.dumps(processing_state['progress'])}\n\n"
                    
                    # Stop streaming if completed or error
                    status = processing_state["progress"].get("status")
                    if status in ["completed", "error"]:
                        break
                        
                elif not processing_state["is_processing"]:
                    # Send idle status
                    yield f"data: {json.dumps({'status': 'idle', 'progress': 0})}\n\n"
                
                await asyncio.sleep(1)  # Update every second
                
        except Exception as e:
            logger.error(f"SSE stream error: {e}")
            yield f"data: {json.dumps({'status': 'error', 'error': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*"
        }
    )

@router.get("/grouped-statutes")
async def get_grouped_statutes(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=1000),
    province: Optional[str] = Query(default=None),
    statute_type: Optional[str] = Query(default=None),
    base_name: Optional[str] = Query(default=None)
):
    """Get paginated grouped statutes with filtering."""
    try:
        result = await phase5_service.get_grouped_statutes(
            page=page,
            page_size=page_size,
            province=province,
            statute_type=statute_type,
            base_name=base_name
        )
        
        return BaseResponse(
            success=True,
            message=f"Retrieved {len(result['items'])} grouped statutes",
            data=result
        )
        
    except Exception as e:
        logger.error(f"Failed to get grouped statutes: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/groups")
async def get_groups(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=1000),
    province: Optional[str] = Query(default=None),
    statute_type: Optional[str] = Query(default=None),
    base_name: Optional[str] = Query(default=None)
):
    """Alias for /grouped-statutes with frontend-expected parameter names."""
    try:
        result = await phase5_service.get_grouped_statutes(
            page=page,
            page_size=limit,  # Frontend uses 'limit' instead of 'page_size'
            province=province,
            statute_type=statute_type,
            base_name=base_name
        )
        
        return BaseResponse(
            success=True,
            message=f"Retrieved {len(result['items'])} grouped statutes",
            data=result
        )
        
    except Exception as e:
        logger.error(f"Failed to get groups: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/collections")
async def get_available_collections():
    """Get available source collections for Phase 5."""
    try:
        collections = await phase5_service.get_available_collections()
        return BaseResponse(
            success=True,
            message=f"Found {len(collections)} available collections",
            data={"collections": collections}
        )
    except Exception as e:
        logger.error(f"Failed to get collections: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/provinces")
async def get_provinces():
    """Get available provinces from source data."""
    try:
        provinces = await phase5_service.get_provinces()
        return BaseResponse(
            success=True,
            message=f"Found {len(provinces)} provinces",
            data={"provinces": provinces}
        )
    except Exception as e:
        logger.error(f"Failed to get provinces: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/statistics")
async def get_statistics():
    """Get general Phase 5 statistics."""
    try:
        # Get status which includes basic statistics
        status = await phase5_service.get_status()
        collections = await phase5_service.get_available_collections()
        
        stats = {
            "total_source_documents": status.get("total_source_documents", 0),
            "grouped_documents": status.get("grouped_documents", 0),
            "available_collections": len(collections),
            "collections": collections,
            "azure_openai_configured": status.get("azure_openai_configured", False),
            "current_progress": status.get("current_progress", 0.0)
        }
        
        return BaseResponse(
            success=True,
            message="Retrieved Phase 5 statistics",
            data=stats
        )
    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stop")
async def stop_processing():
    """Stop the current processing operation."""
    try:
        phase5_service.stop_processing()
        processing_state["is_processing"] = False
        processing_state["progress"] = None
        
        return BaseResponse(
            success=True,
            message="Phase 5 processing stopped"
        )
        
    except Exception as e:
        logger.error(f"Failed to stop processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/statistics/{collection_name}")
async def get_collection_statistics(collection_name: str):
    """Get statistics for a specific collection."""
    try:
        stats = await phase5_service.get_grouping_statistics(collection_name)
        return BaseResponse(
            success=True,
            message=f"Retrieved statistics for {collection_name}",
            data=stats
        )
    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))
async def start_grouping(
    request: Phase5StartRequest,
    background_tasks: BackgroundTasks
):
    """Start the statute grouping and versioning process."""
    if processing_state["is_processing"]:
        raise HTTPException(status_code=400, detail="Phase 5 is already processing")
    
    try:
        # Generate task ID
        import uuid
        task_id = str(uuid.uuid4())
        
        # Set processing state
        processing_state["is_processing"] = True
        processing_state["progress"] = 0
        processing_state["error"] = None
        processing_state["task_id"] = task_id
        
        # Get configuration
        config = request.config or Phase5Config()
        source_collections = request.source_collections
        
        # Start background processing
        background_tasks.add_task(
            _process_grouping_background,
            config,
            source_collections,
            task_id
        )
        
        # Get initial counts for response
        status_data = await phase5_service.get_status()
        
        return Phase5StartResponse(
            success=True,
            message="Phase 5 grouping started successfully",
            task_id=task_id,
            total_statutes=status_data.get("total_source_documents", 0),
            estimated_groups=0  # Will be calculated during processing
        ).dict()
        
    except Exception as e:
        processing_state["is_processing"] = False
        processing_state["error"] = str(e)
        raise HTTPException(status_code=500, detail=f"Failed to start grouping: {str(e)}")

@router.get("/preview-grouping")
async def preview_grouping(
    config_json: Optional[str] = None,
    source_collections: Optional[str] = None,
    preview_size: int = 5
):
    """Preview the grouping results without full processing."""
    try:
        # Parse configuration if provided
        config = None
        if config_json:
            try:
                config_dict = json.loads(config_json)
                config = Phase5Config(**config_dict)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid config JSON: {str(e)}")
        
        # Parse source collections if provided
        collections_list = None
        if source_collections:
            try:
                collections_list = json.loads(source_collections)
                if not isinstance(collections_list, list):
                    raise ValueError("source_collections must be a list")
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid source_collections JSON: {str(e)}")
        
        # Get preview
        preview_data = await phase5_service.preview_grouping(
            config=config,
            source_collections=collections_list,
            preview_size=preview_size
        )
        
        if not preview_data["success"]:
            raise HTTPException(status_code=500, detail=preview_data.get("error", "Preview failed"))
        
        return Phase5PreviewResponse(
            success=True,
            sample_groups=preview_data["sample_groups"],
            total_statutes=preview_data["total_statutes"],
            estimated_groups=preview_data["estimated_groups"],
            preview_size=preview_data["preview_size"]
        ).dict()
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate preview: {str(e)}")

@router.get("/progress")
async def get_progress():
    """Get current processing progress."""
    return BaseResponse(
        success=True,
        message="Progress retrieved successfully",
        data={
            "is_processing": processing_state["is_processing"],
            "progress": processing_state.get("progress", 0),
            "error": processing_state.get("error"),
            "task_id": processing_state.get("task_id")
        }
    ).dict()

@router.post("/stop")
async def stop_processing():
    """Stop the current processing operation."""
    if not processing_state["is_processing"]:
        raise HTTPException(status_code=400, detail="No processing operation is currently running")
    
    try:
        phase5_service.stop_processing()
        processing_state["is_processing"] = False
        processing_state["progress"] = None
        processing_state["error"] = "Stopped by user"
        
        return BaseResponse(
            success=True,
            message="Processing stopped successfully"
        ).dict()
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop processing: {str(e)}")

@router.get("/progress-stream")
async def get_progress_stream():
    """Server-Sent Events endpoint for real-time progress updates."""
    async def generate_progress():
        while processing_state["is_processing"]:
            data = {
                "is_processing": processing_state["is_processing"],
                "progress": processing_state.get("progress", 0),
                "error": processing_state.get("error"),
                "task_id": processing_state.get("task_id"),
                "timestamp": datetime.now().isoformat()
            }
            
            yield f"data: {json.dumps(data)}\n\n"
            await asyncio.sleep(1)  # Update every second
            
        # Send final update
        final_data = {
            "is_processing": False,
            "progress": processing_state.get("progress", 100),
            "error": processing_state.get("error"),
            "task_id": processing_state.get("task_id"),
            "timestamp": datetime.now().isoformat(),
            "completed": True
        }
        yield f"data: {json.dumps(final_data)}\n\n"
    
    return StreamingResponse(
        generate_progress(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream"
        }
    )

@router.get("/grouped-statutes")
async def get_grouped_statutes(
    page: int = 1,
    limit: int = 20,
    group_id: Optional[str] = None,
    base_name: Optional[str] = None
):
    """Get paginated list of grouped statutes."""
    try:
        config = Phase5Config()
        target_db = phase5_service.client.get_database(config.target_database)
        collection = target_db[config.target_collection]
        
        # Build query
        query = {}
        if group_id:
            query["group_id"] = group_id
        if base_name:
            query["base_name"] = {"$regex": base_name, "$options": "i"}
        
        # Get total count
        total = await collection.count_documents(query)
        
        # Get paginated results
        skip = (page - 1) * limit
        cursor = collection.find(query).skip(skip).limit(limit).sort("group_id", 1).sort("version_number", 1)
        
        statutes = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])  # Convert ObjectId to string
            statutes.append(doc)
        
        return BaseResponse(
            success=True,
            message=f"Retrieved {len(statutes)} grouped statutes",
            data={
                "statutes": statutes,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": total,
                    "pages": (total + limit - 1) // limit
                }
            }
        ).dict()
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve grouped statutes: {str(e)}")

@router.get("/groups")
async def get_statute_groups(
    page: int = 1,
    limit: int = 20
):
    """Get paginated list of statute groups."""
    try:
        config = Phase5Config()
        target_db = phase5_service.client.get_database(config.target_database)
        collection = target_db[config.target_collection]
        
        # Aggregate to get group summaries
        pipeline = [
            {
                "$group": {
                    "_id": "$group_id",
                    "base_name": {"$first": "$base_name"},
                    "province": {"$first": "$province"},
                    "statute_type": {"$first": "$statute_type"},
                    "legal_category": {"$first": "$legal_category"},
                    "version_count": {"$sum": 1},
                    "base_statute_id": {
                        "$first": {
                            "$cond": [{"$eq": ["$is_base_version", True]}, "$original_statute_id", None]
                        }
                    },
                    "created_at": {"$min": "$created_at"}
                }
            },
            {"$sort": {"created_at": -1}},
            {"$skip": (page - 1) * limit},
            {"$limit": limit}
        ]
        
        groups = []
        async for doc in collection.aggregate(pipeline):
            groups.append({
                "group_id": doc["_id"],
                "base_name": doc["base_name"],
                "province": doc["province"],
                "statute_type": doc["statute_type"],
                "legal_category": doc["legal_category"],
                "version_count": doc["version_count"],
                "base_statute_id": doc["base_statute_id"],
                "created_at": doc["created_at"]
            })
        
        # Get total groups count
        total_pipeline = [
            {"$group": {"_id": "$group_id"}},
            {"$count": "total"}
        ]
        total_result = await collection.aggregate(total_pipeline).to_list(1)
        total = total_result[0]["total"] if total_result else 0
        
        return BaseResponse(
            success=True,
            message=f"Retrieved {len(groups)} statute groups",
            data={
                "groups": groups,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": total,
                    "pages": (total + limit - 1) // limit
                }
            }
        ).dict()
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve statute groups: {str(e)}")

# Background processing function
async def _process_grouping_background(
    config: Phase5Config,
    source_collections: Optional[List[str]],
    task_id: str
):
    """Background task for processing statute grouping."""
    try:
        async for progress_update in phase5_service.group_and_version_statutes(config, source_collections):
            processing_state["progress"] = progress_update.get("progress", 0)
            
            if progress_update.get("status") == "error":
                processing_state["error"] = progress_update.get("error")
                break
            elif progress_update.get("status") == "completed":
                break
                
    except Exception as e:
        processing_state["error"] = str(e)
    finally:
        processing_state["is_processing"] = False

@router.get("/collections")
async def get_available_collections():
    """Get available collections from Date-Enriched-Batches database."""
    try:
        collections = await phase5_service.get_available_collections()
        return BaseResponse(
            success=True,
            message="Available collections retrieved successfully",
            data={"collections": collections}
        ).dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get collections: {str(e)}")

@router.get("/provinces")
async def get_provinces():
    """Get unique provinces from the database."""
    try:
        provinces = await phase5_service.get_provinces()
        return BaseResponse(
            success=True,
            message="Provinces retrieved successfully",
            data={"provinces": provinces}
        ).dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get provinces: {str(e)}")

@router.post("/analyze-statute")
async def analyze_statute(request: dict):
    """Analyze a single statute for constitutional lineage and legal context"""
    try:
        statute_data = request.get("statute", {})
        
        # Perform constitutional analysis
        constitutional_analysis = await phase5_service.analyze_constitutional_lineage(statute_data)
        
        # Perform legal context analysis
        legal_context = await phase5_service.analyze_legal_context(statute_data)
        
        return BaseResponse(
            success=True,
            message="Statute analysis completed",
            data={
                "constitutional_analysis": constitutional_analysis,
                "legal_context": legal_context,
                "statute_id": str(statute_data.get("_id", "")),
                "analysis_timestamp": datetime.now().isoformat()
            }
        ).dict()
    except Exception as e:
        logger.error(f"Error analyzing statute: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/detect-amendment-chains")
async def detect_amendment_chains(request: dict):
    """Detect amendment chains in a collection"""
    try:
        collection_name = request.get("collection_name")
        
        if not collection_name:
            raise HTTPException(status_code=400, detail="Collection name is required")
        
        # Get statutes from collection
        source_db = phase5_service.client.get_database(phase5_service.default_config.source_database)
        collection = source_db[collection_name]
        statutes = await collection.find({}).to_list(length=None)
        
        # Detect amendment chains
        chains = await phase5_service.detect_amendment_chains(statutes)
        
        return BaseResponse(
            success=True,
            message=f"Detected {len(chains)} amendment chains",
            data={
                "chains": chains,
                "total_chains": len(chains),
                "collection_name": collection_name,
                "analysis_timestamp": datetime.now().isoformat()
            }
        ).dict()
    except Exception as e:
        logger.error(f"Error detecting amendment chains: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/statistics/{collection_name}")
async def get_collection_statistics(collection_name: str):
    """Get detailed statistics for a collection"""
    try:
        stats = await phase5_service.get_grouping_statistics(collection_name)
        
        return BaseResponse(
            success=True,
            message=f"Retrieved statistics for {collection_name}",
            data=stats
        ).dict()
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/export-groups")
async def export_groups(request: dict):
    """Export grouped statutes to JSON or CSV"""
    try:
        format_type = request.get("format", "json").lower()
        collection_name = request.get("collection_name")
        include_analysis = request.get("include_analysis", False)
        
        if not collection_name:
            raise HTTPException(status_code=400, detail="Collection name is required")
        
        # Get groups data (placeholder for now)
        export_data = {
            "export_timestamp": datetime.now().isoformat(),
            "collection_name": collection_name,
            "format": format_type,
            "include_analysis": include_analysis,
            "groups": [],  # Would contain actual grouped data
            "metadata": {
                "total_groups": 0,
                "total_statutes": 0,
                "export_version": "1.0"
            }
        }
        
        return BaseResponse(
            success=True,
            message=f"Export prepared in {format_type} format",
            data=export_data
        ).dict()
    except Exception as e:
        logger.error(f"Error exporting groups: {e}")
        raise HTTPException(status_code=500, detail=str(e))
