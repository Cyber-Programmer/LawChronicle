from fastapi import APIRouter, Depends
from ....core.database import get_db
from ....core.auth import get_current_user, optional_current_user
import pymongo
from shared.types.common import (
    BaseResponse, DatabaseConnectionRequest, DatabaseConnectionResponse,
    FieldAnalysisRequest, FieldAnalysisResponse, PaginationParams
)
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/connect", response_model=BaseResponse)
async def connect_database(
    request: DatabaseConnectionRequest,
    current_user: dict = Depends(optional_current_user)
):
    """Connect to MongoDB database"""
    try:
        # If a specific connection_string is provided, use pymongo to test it
        if request.connection_string:
            try:
                client = pymongo.MongoClient(request.connection_string)
                if request.test_connection:
                    client.admin.command('ping')
                collections = client[request.database_name].list_collection_names()
                db_info = client.admin.command('dbStats')
                return BaseResponse(
                    success=True,
                    message="Database connected successfully",
                    data=DatabaseConnectionResponse(
                        connected=True,
                        database_name=request.database_name,
                        collection_count=len(collections),
                        total_documents=db_info.get('objects', 0),
                        collections=collections
                    )
                )
            except Exception as e:
                from fastapi import HTTPException
                raise HTTPException(status_code=422, detail=str(e))

        # Fallback: use async DB if available
        db = get_db()
        if db is None:
            return BaseResponse(success=False, message="Database not connected", error="No database instance")

        # Use the requested database name when listing collections (but reuse client's connection)
        try:
            client = db.client
            # Test server connectivity
            await client.admin.command('ping')

            target_db_name = request.database_name or client._Database__name if hasattr(client, '_Database__name') else None
            # Prefer the provided database_name
            if not target_db_name:
                target_db_name = client._Database__name if hasattr(client, '_Database__name') else None

            target_db = client[request.database_name]
            collections = await target_db.list_collection_names()
            db_info = await client.admin.command('dbStats')

            return BaseResponse(
                success=True,
                message="Database connected successfully",
                data=DatabaseConnectionResponse(
                    connected=True,
                    database_name=request.database_name,
                    collection_count=len(collections),
                    total_documents=db_info.get('objects', 0),
                    collections=collections
                )
            )
        except Exception as e:
            from fastapi import HTTPException
            raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        from fastapi import HTTPException
        logger.error(f"Database connection failed: {e}")
        if isinstance(e, HTTPException):
            # let FastAPI handle HTTPExceptions so test client sees correct status
            raise e
        return BaseResponse(
            success=False,
            message="Database connection failed",
            error=str(e)
        )

@router.get("/collections", response_model=BaseResponse)
async def get_collections(current_user: dict = Depends(optional_current_user)):
    """Get list of collections in the database"""
    try:
        db = get_db()
        collections = await db.list_collection_names()
        
        # Get document count for each collection
        collection_stats = []
        for collection_name in collections:
            count = await db[collection_name].count_documents({})
            collection_stats.append({
                "name": collection_name,
                "document_count": count
            })
        
        return BaseResponse(
            success=True,
            message="Collections retrieved successfully",
            data=collection_stats
        )
    except Exception as e:
        logger.error(f"Failed to get collections: {e}")
        return BaseResponse(
            success=False,
            message="Failed to retrieve collections",
            error=str(e)
        )

@router.post("/analyze-fields", response_model=BaseResponse)
async def analyze_fields(
    request: FieldAnalysisRequest,
    current_user: dict = Depends(get_current_user)
):
    """Analyze fields in a specific collection"""
    try:
        db = get_db()
        collection = db[request.collection_name]
        
        # Get total document count
        total_docs = await collection.count_documents({})
        
        # Get sample documents
        sample_docs = await collection.find({}).limit(request.sample_size).to_list(request.sample_size)
        
        # Analyze field coverage
        field_coverage = {}
        unique_values = {}
        
        if sample_docs:
            # Get all unique fields from sample
            all_fields = set()
            for doc in sample_docs:
                all_fields.update(doc.keys())
            
            # Calculate field coverage
            for field in all_fields:
                field_docs = await collection.count_documents({field: {"$exists": True}})
                coverage = (field_docs / total_docs) * 100 if total_docs > 0 else 0
                field_coverage[field] = round(coverage, 2)
                
                # Get unique values for text fields (limit to 10)
                if field in ['statute_name', 'title', 'name']:
                    unique_vals = await collection.distinct(field)
                    unique_values[field] = unique_vals[:10]
        
        return BaseResponse(
            success=True,
            message="Field analysis completed",
            data=FieldAnalysisResponse(
                collection_name=request.collection_name,
                total_documents=total_docs,
                field_coverage=field_coverage,
                unique_values=unique_values,
                sample_data=sample_docs
            )
        )
    except Exception as e:
        logger.error(f"Field analysis failed: {e}")
        return BaseResponse(
            success=False,
            message="Field analysis failed",
            error=str(e)
        )

@router.get("/collection/{collection_name}/sample", response_model=BaseResponse)
async def get_sample_documents(
    collection_name: str,
    pagination: PaginationParams = Depends(),
    current_user: dict = Depends(get_current_user)
):
    """Get sample documents from a collection with pagination"""
    try:
        db = get_db()
        collection = db[collection_name]
        
        # Get total count
        total = await collection.count_documents({})
        
        # Calculate skip value
        skip = (pagination.page - 1) * pagination.limit
        
        # Get documents
        cursor = collection.find({}).skip(skip).limit(pagination.limit)
        
        # Apply sorting if specified
        if pagination.sort_by:
            sort_order = 1 if pagination.sort_order == "asc" else -1
            cursor = cursor.sort(pagination.sort_by, sort_order)
        
        documents = await cursor.to_list(pagination.limit)
        
        # Calculate pages
        pages = (total + pagination.limit - 1) // pagination.limit
        
        return BaseResponse(
            success=True,
            message="Sample documents retrieved successfully",
            data={
                "documents": documents,
                "pagination": {
                    "total": total,
                    "page": pagination.page,
                    "limit": pagination.limit,
                    "pages": pages
                }
            }
        )
    except Exception as e:
        logger.error(f"Failed to get sample documents: {e}")
        return BaseResponse(
            success=False,
            message="Failed to retrieve sample documents",
            error=str(e)
        )
