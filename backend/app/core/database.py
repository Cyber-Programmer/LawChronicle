from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure
import logging
from .config import settings

logger = logging.getLogger(__name__)

class Database:
    client: AsyncIOMotorClient = None
    db = None

db = Database()

async def connect_to_mongo():
    """Create database connection"""
    try:
        db.client = AsyncIOMotorClient(settings.mongodb_url)
        db.db = db.client[settings.mongodb_db]
        
        # Test the connection
        await db.client.admin.command('ping')
        logger.info("Successfully connected to MongoDB")
        
        return db.db
    except ConnectionFailure as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error connecting to MongoDB: {e}")
        raise e

async def close_mongo_connection():
    """Close database connection"""
    if db.client:
        db.client.close()
        logger.info("MongoDB connection closed")

async def init_db():
    """Initialize database connection"""
    await connect_to_mongo()
    
    # Create indexes for better performance
    try:
        # Indexes for raw_statutes collection
        await db.db.raw_statutes.create_index("statute_name")
        await db.db.raw_statutes.create_index("created_at")
        
        # Indexes for normalized_statutes collection
        await db.db.normalized_statutes.create_index("statute_name")
        await db.db.normalized_statutes.create_index("normalized_name")
        
        # Indexes for cleaned_statutes collection
        await db.db.cleaned_statutes.create_index("statute_name")
        await db.db.cleaned_statutes.create_index("cleaned_at")
        
        # Indexes for date_enriched_statutes collection
        await db.db.date_enriched_statutes.create_index("statute_name")
        await db.db.date_enriched_statutes.create_index("date_coverage")
        
        # Indexes for versioned_statutes collection
        await db.db.versioned_statutes.create_index("base_name")
        await db.db.versioned_statutes.create_index("version")
        
        # Indexes for section_versions collection
        await db.db.section_versions.create_index("statute_name")
        await db.db.section_versions.create_index("section_id")
        
        # Indexes for metadata collection
        await db.db.metadata.create_index("phase")
        await db.db.metadata.create_index("created_at")
        
        logger.info("Database indexes created successfully")
    except Exception as e:
        logger.warning(f"Failed to create some indexes: {e}")

def get_db():
    """Get database instance"""
    return db.db
