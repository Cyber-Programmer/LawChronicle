from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from datetime import datetime
import logging

MONGODB_URI = "mongodb://localhost:27017"
DATABASE_NAME = settings.mongodb_db

from ....core.config import settings
from ....core.database import db

logger = logging.getLogger(__name__)
router = APIRouter()

COLLECTION_NAME = "raw_statutes"
COLLECTION_NAME = "raw_statutes"

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
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
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
        client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        db = client[DATABASE_NAME]
        collection = db[COLLECTION_NAME]
        
        # Get total document count
        total_docs = collection.count_documents({})
        
        if total_docs == 0:
            return {"message": "Collection is empty", "fields": {}}
        
        # Get multiple sample documents to identify all fields
        sample_docs = list(collection.find().limit(100))
        if not sample_docs:
            return {"message": "No documents found", "fields": {}}
        
        # Collect all unique field names from sample documents
        all_fields = set()
        for doc in sample_docs:
            all_fields.update(doc.keys())
        
        fields = list(all_fields)
        field_stats = {}
        
        # Analyze each field
        for field in fields:
            # Count documents with this field
            field_count = collection.count_documents({field: {"$exists": True, "$ne": None}})
            
            # Count documents with non-empty values
            non_empty_count = collection.count_documents({
                field: {"$exists": True, "$ne": None, "$nin": ["", None]}
            })
            
            # Get sample values for this field (avoid distinct on large datasets)
            sample_pipeline = [
                {"$match": {field: {"$exists": True, "$nin": [None, ""]}}},
                {"$sample": {"size": 5}},
                {"$project": {field: 1, "_id": 0}}
            ]
            try:
                sample_docs = list(collection.aggregate(sample_pipeline))
                sample_values = [doc.get(field) for doc in sample_docs if doc.get(field) is not None][:5]
            except Exception as e:
                logger.warning(f"Failed to get sample values for field {field}: {e}")
                sample_values = []
            
            # Calculate percentages
            coverage_percentage = (field_count / total_docs) * 100 if total_docs > 0 else 0
            non_empty_percentage = (non_empty_count / total_docs) * 100 if total_docs > 0 else 0
            
            field_stats[field] = {
                "total_documents": total_docs,
                "field_present": field_count,
                "non_empty_values": non_empty_count,
                "coverage_percentage": round(coverage_percentage, 2),
                "non_empty_percentage": round(non_empty_percentage, 2),
                "missing_count": total_docs - field_count,
                "empty_count": field_count - non_empty_count,
                "sample_values": sample_values,
                "field_type": type(sample_values[0]).__name__ if sample_values else "unknown"
            }
        
        client.close()
        
        return {
            "total_documents": total_docs,
            "total_fields": len(fields),
            "field_statistics": field_stats,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get field statistics: {str(e)}"
        )

@router.get("/sample-data")
async def get_sample_data(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Documents per page"),
    field_filter: Optional[str] = Query(None, description="Filter by field name")
):
    """Get paginated sample data from the collection"""
    try:
        client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        db = client[DATABASE_NAME]
        collection = db[COLLECTION_NAME]
        
        # Calculate skip value for pagination
        skip = (page - 1) * page_size
        
        # Build query filter
        query_filter = {}
        if field_filter:
            query_filter[field_filter] = {"$exists": True, "$ne": None}
        
        # Get total count for pagination
        total_count = collection.count_documents(query_filter)
        
        # Get documents for current page
        documents = list(collection.find(
            query_filter,
            {"_id": 0}  # Exclude MongoDB _id field
        ).skip(skip).limit(page_size))
        
        # Calculate pagination info
        total_pages = (total_count + page_size - 1) // page_size
        
        client.close()
        
        return {
            "documents": documents,
            "pagination": {
                "current_page": page,
                "page_size": page_size,
                "total_documents": total_count,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_previous": page > 1
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get sample data: {str(e)}"
        )

@router.get("/statute-names")
async def get_statute_names():
    """Get unique statute names and their distribution"""
    try:
        client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        db = client[DATABASE_NAME]
        collection = db[COLLECTION_NAME]
        
        # Get unique statute names (assuming there's a 'name' or 'title' field)
        # We'll try common field names for statute names
        possible_name_fields = ["Statute_Name", "name", "title", "statute_name", "statute_title", "document_name", "Act_Ordinance"]
        
        statute_names = []
        field_used = None
        
        for field in possible_name_fields:
            try:
                names = list(collection.distinct(field))
                if names and len(names) > 0:
                    statute_names = names
                    field_used = field
                    break
            except (KeyError, TypeError, AttributeError) as e:
                logger.debug(f"Field {field} not suitable for statute names: {e}")
                continue
        
        if not statute_names:
            # If no specific name field found, get all unique values from first few fields
            sample_doc = collection.find_one()
            if sample_doc:
                for field, value in sample_doc.items():
                    if isinstance(value, str) and len(value) < 200:  # Reasonable string length
                        try:
                            names = list(collection.distinct(field))
                            if names and len(names) > 0:
                                statute_names = names[:100]  # Limit to first 100
                                field_used = field
                                break
                        except (KeyError, TypeError, AttributeError) as e:
                            logger.debug(f"Field {field} not suitable for statute names: {e}")
                            continue
        
        # Get distribution count for each name
        name_distribution = {}
        if field_used:
            for name in statute_names[:50]:  # Limit to first 50 for performance
                count = collection.count_documents({field_used: name})
                name_distribution[name] = count
        
        client.close()
        
        return {
            "field_used": field_used,
            "total_unique_names": len(statute_names),
            "names_sample": statute_names[:20],  # Return first 20 names
            "name_distribution": name_distribution,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get statute names: {str(e)}"
        )

@router.get("/health")
async def get_database_health():
    """Get database health status and performance metrics"""
    try:
        client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        
        # Test connection
        start_time = datetime.now()
        client.admin.command('ping')
        response_time = (datetime.now() - start_time).total_seconds() * 1000
        
        # Get server info
        server_info = client.server_info()
        
        # Get database stats
        db = client[DATABASE_NAME]
        db_stats = db.command("dbStats")
        
        client.close()
        
        return {
            "status": "healthy",
            "response_time_ms": round(response_time, 2),
            "server_version": server_info.get("version", "unknown"),
            "database_size_bytes": db_stats.get("dataSize", 0),
            "storage_size_bytes": db_stats.get("storageSize", 0),
            "index_size_bytes": db_stats.get("indexSize", 0),
            "collections": db_stats.get("collections", 0),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@router.get("/analyze")
async def analyze_database_structure():
    """Comprehensive database structure analysis"""
    try:
        client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        db = client[DATABASE_NAME]
        collection = db[COLLECTION_NAME]
        
        # Get basic collection info
        total_docs = collection.count_documents({})
        
        if total_docs == 0:
            return {"message": "Collection is empty", "analysis": {}}
        
        # Get sample documents for analysis
        sample_docs = list(collection.find().limit(100))
        
        # Analyze field structure
        field_analysis = {}
        for doc in sample_docs:
            for field, value in doc.items():
                if field not in field_analysis:
                    field_analysis[field] = {
                        "types": set(),
                        "sample_values": set(),
                        "null_count": 0,
                        "empty_count": 0
                    }
                
                # Track data types
                if value is None:
                    field_analysis[field]["null_count"] += 1
                elif value == "":
                    field_analysis[field]["empty_count"] += 1
                else:
                    field_analysis[field]["types"].add(type(value).__name__)
                    if len(field_analysis[field]["sample_values"]) < 5:
                        field_analysis[field]["sample_values"].add(str(value)[:100])
        
        # Convert sets to lists for JSON serialization
        for field in field_analysis:
            field_analysis[field]["types"] = list(field_analysis[field]["types"])
            field_analysis[field]["sample_values"] = list(field_analysis[field]["sample_values"])
        
        client.close()
        
        return {
            "total_documents_analyzed": len(sample_docs),
            "total_documents_in_collection": total_docs,
            "field_analysis": field_analysis,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze database structure: {str(e)}"
        )
