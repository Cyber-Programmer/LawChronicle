from fastapi import APIRouter, HTTPException
from datetime import datetime

router = APIRouter()

@router.get("/sample-doc-debug")
async def get_sample_doc_debug():
    if db.db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    collection = db.db[COLLECTION_NAME]
    doc = await collection.find_one()
    if not doc:
        return {"message": "No documents found"}
    # Convert ObjectId to string for JSON serialization
    if "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc
    @router.get("/sample-data")
    async def get_sample_data(page: int = 1, page_size: int = 10):
        if db.db is None:
            raise HTTPException(status_code=503, detail="Database not connected")
        collection = db.db[COLLECTION_NAME]
        skip = (page - 1) * page_size
        documents = await collection.find({}).skip(skip).limit(page_size).to_list(length=page_size)
        for doc in documents:
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
        return {
            "data": documents,
            "page": page,
            "page_size": page_size,
            "count": len(documents)
        }
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from datetime import datetime
import logging

from ....core.config import settings
from ....core.database import db

logger = logging.getLogger(__name__)
router = APIRouter()

COLLECTION_NAME = "raw_statutes"

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        if db.db is None:
            return {
                "status": "unhealthy",
                "error": "Database not connected",
                "timestamp": datetime.now().isoformat()
            }
        
        # Test database connection
        collection = db.db[COLLECTION_NAME]
        doc_count = await collection.count_documents({})
        
        return {
            "status": "healthy",
            "database_connected": True,
            "collection": COLLECTION_NAME,
            "document_count": doc_count,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@router.get("/connect")
async def test_database_connection():
    """Test connection to MongoDB database"""
    try:
        if db.db is None:
            raise HTTPException(status_code=503, detail="Database not connected")
        
        # Test specific collection
        collection = db.db[COLLECTION_NAME]
        
        # Get basic collection info
        doc_count = await collection.count_documents({})
        
        return {
            "status": "connected",
            "database": settings.mongodb_db,
            "collection": COLLECTION_NAME,
            "document_count": doc_count,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Database connection failed: {str(e)}"
        )

@router.get("/database-info")
async def get_database_info():
    """Get comprehensive database information"""
    try:
        if db.db is None:
            raise HTTPException(status_code=503, detail="Database not connected")
        
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

@router.get("/field-stats")
async def get_field_statistics():
    """Get comprehensive field statistics for the collection"""
    try:
        if db.db is None:
            raise HTTPException(status_code=503, detail="Database not connected")
        collection = db.db[COLLECTION_NAME]
        total_docs = await collection.count_documents({})
        if total_docs == 0:
            return {
                "message": "Collection is empty",
                "total_documents": 0,
                "fields": []
            }
        sample_docs = await collection.find({}).limit(100).to_list(length=100)
        all_fields = set()
        for doc in sample_docs:
            all_fields.update(doc.keys())
        all_fields.discard("_id")
        field_stats = []
        for field in sorted(all_fields):
            try:
                present_count = await collection.count_documents({field: {"$exists": True}})
                missing_count = total_docs - present_count
                non_empty_count = await collection.count_documents({field: {"$exists": True, "$nin": [None, ""]}})
                empty_count = present_count - non_empty_count
                sample_pipeline = [
                    {"$match": {field: {"$exists": True, "$nin": [None, ""]}}},
                    {"$sample": {"size": 5}},
                    {"$project": {field: 1, "_id": 0}}
                ]
                try:
                    sample_docs = await collection.aggregate(sample_pipeline).to_list(length=5)
                    sample_values = [doc.get(field) for doc in sample_docs if doc.get(field) is not None][:5]
                except Exception as e:
                    logger.warning(f"Failed to get sample values for field {field}: {e}")
                    sample_values = []
                percentage = (non_empty_count / total_docs) * 100 if total_docs > 0 else 0
                field_stats.append({
                    "field_name": field,
                    "present": present_count,
                    "missing": missing_count,
                    "non_empty": non_empty_count,
                    "empty": empty_count,
                    "total_documents": total_docs,
                    "percentage_populated": round(percentage, 2),
                    "sample_values": sample_values
                })
            except Exception as e:
                logger.warning(f"Error analyzing field {field}: {e}")
                continue
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

@router.get("/statute-names")
async def get_statute_names():
    """Get unique statute names and their distribution"""
    try:
        if db.db is None:
            raise HTTPException(status_code=503, detail="Database not connected")
        collection = db.db[COLLECTION_NAME]
        possible_fields = ["Statute_Name", "statute_name", "name", "title", "statute", "law_name"]
        field_used = None
        for field in possible_fields:
            sample_doc = await collection.find_one({field: {"$exists": True, "$ne": None, "$ne": ""}})
            if sample_doc:
                field_used = field
                break
        if not field_used:
            sample_doc = await collection.find_one({})
            if sample_doc:
                for key, value in sample_doc.items():
                    if isinstance(value, str) and len(value) > 0 and key != "_id":
                        field_used = key
                        break
        if not field_used:
            return {
                "field_used": None,
                "total_unique_names": 0,
                "names_sample": [],
                "name_distribution": {},
                "timestamp": datetime.now().isoformat()
            }
        pipeline = [
            {"$match": {field_used: {"$exists": True, "$ne": None, "$ne": ""}}},
            {"$group": {"_id": f"${field_used}", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        results = await collection.aggregate(pipeline).to_list(length=None)
        name_distribution = {result["_id"]: result["count"] for result in results}
        unique_names = list(name_distribution.keys())
        total_unique = len(unique_names)
        names_sample = unique_names[:50]
        return {
            "field_used": field_used,
            "total_unique_names": total_unique,
            "names_sample": names_sample,
            "name_distribution": name_distribution,
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
