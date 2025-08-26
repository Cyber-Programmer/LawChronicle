def ensure_db_connected():
    if db.db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient
import pymongo
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from datetime import datetime
import logging

from ....core.config import settings
from ....core.database import db

logger = logging.getLogger(__name__)
router = APIRouter()

COLLECTION_NAME = "raw_statutes"

@router.get("/connect")
async def test_database_connection():
    """Test connection to MongoDB database"""
    ensure_db_connected()
    try:
        # If async DB is not connected, try a local pymongo client for test scenarios
        if db.db is None:
            client = pymongo.MongoClient(settings.mongodb_url)
            collection = client[settings.mongodb_db][COLLECTION_NAME]
            doc_count = collection.count_documents({})
        else:
            collection = db.db[COLLECTION_NAME]
            doc_count = await collection.count_documents({})

        return {
            "status": "connected",
            "database": settings.mongodb_db,
            "collection": COLLECTION_NAME,
            "document_count": doc_count,
            "timestamp": datetime.now().isoformat()
        }
    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        logger.error(f"Database connection failed: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Database connection failed: {str(e)}"
        )

@router.get("/database-info")
async def get_database_info():
    """Get comprehensive database information"""
    try:
        if db.db is None:
            # Fallback to pymongo for tests
            client = pymongo.MongoClient(settings.mongodb_url)
            stats = client[settings.mongodb_db].command("collStats", COLLECTION_NAME)
            sample_doc = client[settings.mongodb_db][COLLECTION_NAME].find_one()
        else:
            collection = db.db[COLLECTION_NAME]
            # Get collection stats
            stats = await db.db.command("collStats", COLLECTION_NAME)
            # Get sample document for schema analysis
            sample_doc = await collection.find_one()
        
        # Get field names from sample document
        fields = list(sample_doc.keys()) if sample_doc else []
        
        return {
            "database_name": settings.mongodb_db,
            "collection_name": COLLECTION_NAME,
            "total_documents": stats.get("count", 0),
            "total_size_bytes": stats.get("size", 0),
            "average_document_size": stats.get("avgObjSize", 0),
            "index_count": stats.get("nindexes", 0),
            "fields": fields,
            "sample_document_keys": fields,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Database info error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get database info: {str(e)}"
        )

async def _get_field_names(collection):
    """Helper function to get field names from sample documents"""
    sample_docs = await collection.find({}).limit(100).to_list(length=100)
    all_fields = set()
    for doc in sample_docs:
        all_fields.update(doc.keys())
    
    # Remove _id field for analysis
    all_fields.discard("_id")
    return sorted(all_fields)

async def _get_field_sample_values(collection, field):
    """Helper function to get sample values for a field"""
    sample_pipeline = [
        {"$match": {field: {"$exists": True, "$nin": [None, ""]}}},
        {"$sample": {"size": 5}},
        {"$project": {field: 1, "_id": 0}}
    ]
    
    try:
        sample_docs = await collection.aggregate(sample_pipeline).to_list(length=5)
        return [doc.get(field) for doc in sample_docs if doc.get(field) is not None][:5]
    except Exception as e:
        logger.warning(f"Failed to get sample values for field {field}: {e}")
        return []

async def _collect_field_stats(collection, field, total_docs):
    """Helper function to collect statistics for a single field"""
    try:
        # Count documents with non-empty values
        non_empty_count = await collection.count_documents({
            field: {"$exists": True, "$nin": [None, ""]}
        })
        
        # Get sample values
        sample_values = await _get_field_sample_values(collection, field)
        
        # Calculate percentage
        percentage = (non_empty_count / total_docs) * 100 if total_docs > 0 else 0
        
        return {
            "field_name": field,
            "non_empty_count": non_empty_count,
            "total_documents": total_docs,
            "percentage_populated": round(percentage, 2),
            "sample_values": sample_values
        }
    except Exception as e:
        logger.warning(f"Error analyzing field {field}: {e}")
        return None

@router.get("/field-stats")
async def get_field_statistics():
    """Get comprehensive field statistics for the collection"""
    try:
        if db.db is None:
            raise HTTPException(status_code=503, detail="Database not connected")
        
        collection = db.db[COLLECTION_NAME]
        
        # Get total document count
        total_docs = await collection.count_documents({})
        
        if total_docs == 0:
            return {
                "message": "Collection is empty",
                "total_documents": 0,
                "fields": []
            }
        
        # Get all field names
        all_fields = await _get_field_names(collection)
        
        # Collect statistics for each field
        field_stats = []
        for field in all_fields:
            stats = await _collect_field_stats(collection, field, total_docs)
            if stats:
                field_stats.append(stats)
        
        return {
            "total_documents": total_docs,
            "total_fields": len(field_stats),
            "field_statistics": field_stats,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Field statistics error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get field statistics: {str(e)}"
        )

async def _try_get_distinct_names(collection, field, limit):
    """Helper function to get distinct statute names from a field"""
    try:
        names = await collection.distinct(field)
        if names:
            return names[:limit], field
    except (KeyError, TypeError, AttributeError) as e:
        logger.debug(f"Field {field} not suitable for distinct query: {e}")
    return [], None

async def _try_get_names_from_docs(collection, field, limit):
    """Helper function to get statute names from sample documents"""
    try:
        sample_docs = await collection.find({field: {"$exists": True}}).limit(limit).to_list(length=limit)
        if sample_docs:
            names = [doc.get(field) for doc in sample_docs if doc.get(field)]
            if names:
                return names, field
    except (KeyError, TypeError, AttributeError) as e:
        logger.debug(f"Field {field} not suitable for document query: {e}")
    return [], None

async def _find_statute_names(collection, limit):
    """Find statute names using various methods"""
    # Common field names for statute names
    statute_name_fields = [
        "Statute_Name", "statute_name", "StatuteName", "Name", "name",
        "Act_Name", "act_name", "ActName", "Title", "title"
    ]
    
    # Try both distinct and document methods in one loop
    for field in statute_name_fields:
        names, field_used = await _try_get_distinct_names(collection, field, limit)
        if names:
            return names, field_used
        names, field_used = await _try_get_names_from_docs(collection, field, limit)
        if names:
            return names, field_used
            
    return [], None

@router.get("/statute-names")
async def get_statute_names(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0)
):
    """Get paginated list of statute names and total unique count from the database"""
    try:
        if db.db is None:
            raise HTTPException(status_code=503, detail="Database not connected")

        collection = db.db[COLLECTION_NAME]
        field_used = "Statute_Name"

        # Get all unique statute names
        all_names = await collection.distinct(field_used)
        total_count = len(all_names)

        # Paginate
        paginated_names = all_names[offset:offset+limit]

        return {
            "statute_names": paginated_names,
            "count": total_count,
            "field_used": field_used,
            "limit": limit,
            "offset": offset,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Statute names error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get statute names: {str(e)}"
        )

@router.get("/sample-documents")
async def get_sample_documents(limit: int = Query(default=5, le=50)):
    """Get sample documents from the collection"""
    try:
        if db.db is None:
            raise HTTPException(status_code=503, detail="Database not connected")
        
        collection = db.db[COLLECTION_NAME]
        
        # Get sample documents
        documents = await collection.find({}).limit(limit).to_list(length=limit)
        
        # Convert ObjectId to string for JSON serialization
        for doc in documents:
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
        
        return {
            "sample_documents": documents,
            "count": len(documents),
            "limit": limit,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Sample documents error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get sample documents: {str(e)}"
        )

# Alias endpoint for frontend compatibility
@router.get("/sample-data")
@router.get("/sample-data")
async def get_sample_data(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    field_filter: str = Query(default=None, description="Optional field filter")
):
    """Returns paginated sample documents and pagination info."""
    try:
        if db.db is None:
            raise HTTPException(status_code=503, detail="Database not connected")

        collection = db.db[COLLECTION_NAME]

        query = {}
        if field_filter:
            query = {field_filter: {"$exists": True, "$nin": [None, ""]}}

        total_documents = await collection.count_documents(query)
        total_pages = max(1, (total_documents + page_size - 1) // page_size)
        skip = (page - 1) * page_size

        documents = await collection.find(query).skip(skip).limit(page_size).to_list(length=page_size)
        for doc in documents:
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])

        pagination = {
            "current_page": page,
            "page_size": page_size,
            "total_documents": total_documents,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_previous": page > 1
        }

        return {
            "documents": documents,
            "pagination": pagination,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Sample data error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get sample data: {str(e)}"
        )
