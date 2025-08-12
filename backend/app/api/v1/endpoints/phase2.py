from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from typing import Dict, Any, List, Optional, Union
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
from ....core.database import get_db
from ....core.config import settings
import tempfile
import subprocess
import os
import json
import re
from datetime import datetime, timezone
from shared.types.common import BaseResponse
import logging

# Set up logging
logger = logging.getLogger(__name__)

# Configure logger to show INFO and DEBUG messages
# This ensures all normalization processing steps are visible
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger.setLevel(logging.INFO)

router = APIRouter()

# Configuration model for database and collection settings
class NormalizationConfig(BaseModel):
    source_collection: str = "raw_statutes"
    target_collection: str = "normalized_statutes"
    database_name: Optional[str] = None  # If None, use settings.mongodb_db
    cleaned_collection: str = "normalized_statutes"
    sorted_collection: str = "sorted_statutes"

# Default MongoDB connection settings - Updated to use correct collection names
MONGODB_URI = settings.mongodb_url
DEFAULT_DATABASE_NAME = settings.mongodb_db
DEFAULT_SOURCE_COLLECTION = "raw_statutes"  # Input collection
DEFAULT_TARGET_COLLECTION = "normalized_statutes"  # Output collection
DEFAULT_CLEANED_COLLECTION = "normalized_statutes"  # Intermediate collection
DEFAULT_SORTED_COLLECTION = "sorted_statutes"  # Final collection

# Field name constants to ensure consistency and avoid case sensitivity issues
FIELD_NAMES = {
    # Source document fields (as they appear in raw data)
    "STATUTE_NAME": "Statute_Name",
    "ACT_ORDINANCE": "Act_Ordinance", 
    "SECTION": "Section",
    "YEAR": "Year",
    "DATE": "Date",
    "STATUTE": "Statute",
    "STATUTE_HTML": "Statute_HTML",
    "STATUTE_RAG_CONTENT": "Statute_RAG_Content",
    
    # Normalized document fields (standardized lowercase)
    "statute_name": "statute_name",
    "act_ordinance": "act_ordinance",
    "section_number": "section_number", 
    "section_definition": "section_definition",
    "year": "year",
    "date": "date",
    "statute_content": "statute_content",
    "statute_html": "statute_html",
    "statute_rag_content": "statute_rag_content",
    
    # Metadata fields
    "normalized_at": "normalized_at",
    "normalization_version": "normalization_version",
    "original_id": "original_id"
}

# Helper function to get field names safely
def get_source_field(field_key: str) -> str:
    """Get the source field name (as it appears in raw data)"""
    return FIELD_NAMES.get(field_key, field_key)

def get_normalized_field(field_key: str) -> str:
    """Get the normalized field name (standardized format)"""
    return FIELD_NAMES.get(field_key, field_key)

def get_collection_names(config: NormalizationConfig) -> Dict[str, str]:
    """Get collection names from config or defaults"""
    return {
        "source": config.source_collection or DEFAULT_SOURCE_COLLECTION,
        "target": config.target_collection or DEFAULT_TARGET_COLLECTION,
        "cleaned": config.cleaned_collection or DEFAULT_CLEANED_COLLECTION,
        "sorted": config.sorted_collection or DEFAULT_SORTED_COLLECTION,
        "database": config.database_name or DEFAULT_DATABASE_NAME
    }

async def detect_actual_field_names(db, collection_name: str = None, config: NormalizationConfig = None) -> Dict[str, str]:
    """
    Dynamically detect actual field names from the database to handle case sensitivity issues.
    This function analyzes the actual data structure and maps expected fields to actual fields.
    """
    try:
        if collection_name is None:
            if config:
                collection_name = config.source_collection or DEFAULT_SOURCE_COLLECTION
            else:
                collection_name = DEFAULT_SOURCE_COLLECTION
            
        # Get a sample document to analyze field names
        sample_doc = await db[collection_name].find_one()
        if not sample_doc:
            logger.warning(f"No documents found in {collection_name} for field detection")
            return {}
        
        actual_fields = list(sample_doc.keys())
        logger.info(f"Detected {len(actual_fields)} actual fields in {collection_name}: {actual_fields}")
        
        # Map expected fields to actual fields (case-insensitive matching)
        field_mapping = {}
        for expected_key, expected_field in FIELD_NAMES.items():
            if expected_key.startswith("STATUTE_NAME") or expected_key.startswith("ACT_ORDINANCE") or expected_key.startswith("SECTION"):
                # For key fields, try to find case-insensitive matches
                for actual_field in actual_fields:
                    if actual_field.lower() == expected_field.lower():
                        field_mapping[expected_key] = actual_field
                        logger.info(f"Mapped {expected_key} -> {actual_field}")
                        break
                else:
                    # If no exact match found, log a warning
                    logger.warning(f"No match found for expected field: {expected_field}")
                    field_mapping[expected_key] = expected_field  # Keep original as fallback
        
        return field_mapping
        
    except Exception as e:
        logger.error(f"Field detection failed: {str(e)}")
        return {}

class NormalizationScriptGenerator:
    """Generates Python scripts for database normalization"""
    
    @staticmethod
    def generate_statute_name_normalizer(config: Dict[str, Any]) -> str:
        """Generate Python script for statute name normalization"""
        script = f'''
# -*- coding: utf-8 -*-
import sys
import os

# Add the current directory to Python path to find packages
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

try:
    import pymongo
            print("[SUCCESS] pymongo imported successfully")
except ImportError as e:
    print(f"❌ Failed to import pymongo: {{e}}")
    print(f"Python executable: {{sys.executable}}")
    print(f"Python path: {{sys.path}}")
    print(f"Current working directory: {{os.getcwd()}}")
    sys.exit(1)

import re
from datetime import datetime
from typing import Dict, Any

# Configuration - Updated collection names
MONGO_URI = "{config.get('mongo_uri', MONGODB_URI)}"
SOURCE_DB = "{config.get('source_db', DEFAULT_DATABASE_NAME)}"
SOURCE_COLL = "{config.get('source_collection', DEFAULT_SOURCE_COLLECTION)}"
TARGET_DB = "{config.get('target_db', DEFAULT_DATABASE_NAME)}"
TARGET_COLL = "{config.get('target_collection', DEFAULT_TARGET_COLLECTION)}"

# Field name constants to ensure consistency and avoid case sensitivity issues
FIELD_NAMES = {{
    # Source document fields (as they appear in raw data)
    "STATUTE_NAME": "Statute_Name",
    "ACT_ORDINANCE": "Act_Ordinance", 
    "SECTION": "Section",
    "YEAR": "Year",
    "DATE": "Date",
    "STATUTE": "Statute",
    "STATUTE_HTML": "Statute_HTML",
    "STATUTE_RAG_CONTENT": "Statute_RAG_Content",
    
    # Normalized document fields (standardized lowercase)
    "statute_name": "statute_name",
    "act_ordinance": "act_ordinance",
    "section_number": "section_number", 
    "section_definition": "section_definition",
    "year": "year",
    "date": "date",
    "statute_content": "statute_content",
    "statute_html": "statute_html",
    "statute_rag_content": "statute_rag_content",
    
    # Metadata fields
    "normalized_at": "normalized_at",
    "normalization_version": "normalization_version",
    "original_id": "original_id"
}}

# Helper function to get field names safely
def get_source_field(field_key: str) -> str:
    """Get the source field name (as it appears in raw data)"""
    return FIELD_NAMES.get(field_key, field_key)

def get_normalized_field(field_key: str) -> str:
    """Get the normalized field name (standardized format)"""
    return FIELD_NAMES.get(field_key, field_key)

def normalize_statute_name(name: str) -> str:
    """Normalize statute names with enhanced logic"""
    if not name:
        return "UNKNOWN"
    
    # Convert to string and strip whitespace
    name = str(name).strip()
    
    # Remove extra whitespace and newlines
    name = re.sub(r'\\s+', ' ', name)
    
    # Handle common legal prefixes and suffixes
    # Remove "Act", "Regulation", "Ordinance" from the beginning for better sorting
    prefixes_to_remove = ["The ", "An ", "A "]
    for prefix in prefixes_to_remove:
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    
    # Convert to title case
    name = name.title()
    
    # Standardize common legal terms
    name = name.replace('Act', 'Act')
    name = name.replace('Regulation', 'Regulation')
    name = name.replace('Ordinance', 'Ordinance')
    
    # Remove special characters but keep spaces, hyphens, dots, and parentheses
    name = re.sub(r'[^\\w\\s\\-\\.\\(\\)]', '', name)
    
    # Clean up multiple spaces again
    name = re.sub(r'\\s+', ' ', name).strip()
    
    return name if name else "UNKNOWN"

def extract_section_info(section_text: str) -> Dict[str, Any]:
    """Extract section number and definition from section text"""
    if not section_text:
        return {{"section_number": "", "definition": ""}}
    
    section_text = str(section_text).strip()
    
    # Try to extract section number (e.g., "9.", "Section 9", "9")
    section_match = re.search(r'(?:Section\\s*)?(\\d+)(?:\\.|\\s|$)', section_text)
    section_number = section_match.group(1) if section_match else ""
    
    # Extract definition (everything after the section number)
    if section_match:
        definition = section_text[section_match.end():].strip()
        # Remove leading punctuation
        definition = re.sub(r'^[\\s\\-\\.]+', '', definition)
    else:
        definition = section_text
    
    return {{
        "section_number": section_number,
        "definition": definition
    }}

def normalize_document(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a complete document"""
    normalized_doc = doc.copy()
    
    # Normalize statute names in various fields using field name constants
    statute_name_field = get_source_field("STATUTE_NAME")
    if statute_name_field in doc:
        normalized_doc[get_normalized_field("statute_name")] = normalize_statute_name(doc[statute_name_field])
    
    act_ordinance_field = get_source_field("ACT_ORDINANCE")
    if act_ordinance_field in doc:
        normalized_doc[get_normalized_field("act_ordinance")] = normalize_statute_name(doc[act_ordinance_field])
    
    # Handle section information
    section_field = get_source_field("SECTION")
    if section_field in doc:
        section_info = extract_section_info(doc[section_field])
        normalized_doc[get_normalized_field("section_number")] = section_info['section_number']
        normalized_doc[get_normalized_field("section_definition")] = section_info['definition']
    
    # Normalize year and date fields
    year_field = get_source_field("YEAR")
    if year_field in doc and doc[year_field]:
        try:
            year = int(doc[year_field])
            if 1900 <= year <= 2100:  # Valid year range
                normalized_doc[get_normalized_field("year")] = year
            else:
                normalized_doc[get_normalized_field("year")] = None
        except (ValueError, TypeError):
            normalized_doc[get_normalized_field("year")] = None
    
    date_field = get_source_field("DATE")
    if date_field in doc and doc[date_field]:
        # Keep original date format for now, could be enhanced with date parsing
        normalized_doc[get_normalized_field("date")] = str(doc[date_field]).strip()
    
    # Clean content fields
    statute_field = get_source_field("STATUTE")
    if statute_field in doc and doc[statute_field]:
        normalized_doc[get_normalized_field("statute_content")] = str(doc[statute_field]).strip()
    
    statute_html_field = get_source_field("STATUTE_HTML")
    if statute_html_field in doc and doc[statute_html_field]:
        normalized_doc[get_normalized_field("statute_html")] = str(doc[statute_html_field]).strip()
    
    statute_rag_field = get_source_field("STATUTE_RAG_CONTENT")
    if statute_rag_field in doc and doc[statute_rag_field]:
        normalized_doc[get_normalized_field("statute_rag_content")] = str(doc[statute_rag_field]).strip()
    
    # Add normalization metadata
    normalized_doc[get_normalized_field("normalized_at")] = datetime.now()
    normalized_doc[get_normalized_field("normalization_version")] = "2.0"
    normalized_doc[get_normalized_field("original_id")] = str(doc.get('_id'))
    
    return normalized_doc

def main():
    try:
        print(f"Starting statute name normalization...")
        print(f"Python executable: {{sys.executable}}")
        print(f"Python version: {{sys.version}}")
        print(f"Current working directory: {{os.getcwd()}}")
        print(f"Connecting to MongoDB at: {{MONGO_URI}}")
        print(f"Source DB: {{SOURCE_DB}}, Collection: {{SOURCE_COLL}}")
        print(f"Target DB: {{TARGET_DB}}, Collection: {{TARGET_COLL}}")
        
        # Test MongoDB connection
        try:
            client = pymongo.MongoClient(MONGO_URI)
            client.admin.command('ping')
            print("[SUCCESS] MongoDB connection successful")
        except Exception as conn_error:
            print(f"❌ MongoDB connection failed: {{conn_error}}")
            return
        
        source_col = client[SOURCE_DB][SOURCE_COLL]
        target_col = client[TARGET_DB][TARGET_COLL]
        
        # Check if source collection exists and has data
        try:
            source_count = source_col.count_documents({{}})
            print(f"Source collection has {{source_count}} documents")
        except Exception as count_error:
            print(f"❌ Error counting documents: {{count_error}}")
            return
        
        if source_count == 0:
            print("❌ Source collection is empty")
            return
        
        # Clear target collection
        try:
            target_col.delete_many({{}})
            print("[SUCCESS] Cleared target collection")
        except Exception as clear_error:
            print(f"❌ Error clearing target collection: {{clear_error}}")
            return
        
        # Process documents with enhanced logging
        total_docs = source_count
        processed = 0
        errors = 0
        skipped = 0
        
        print(f"Starting enhanced normalization of {{total_docs}} documents...")
        print(f"Processing documents from {{SOURCE_COLL}} to {{TARGET_COLL}}...")
        
        for doc in source_col.find():
            try:
                # Log document being processed
                doc_id = doc.get('_id', 'unknown')
                print(f"Processing document {{doc_id}}...")
                
                normalized_doc = normalize_document(doc)
                
                # Insert into target collection
                result = target_col.insert_one(normalized_doc)
                processed += 1
                
                print(f"[SUCCESS] Document {{doc_id}} normalized and inserted with ID: {{result.inserted_id}}")
                
                if processed % 10 == 0:  # Log every 10 documents for better visibility
                    print(f"Progress: {{processed}}/{{total_docs}} documents processed...")
                    
            except Exception as doc_error:
                print(f"❌ Error processing document {{doc.get('_id', 'unknown')}}: {{str(doc_error)}}")
                errors += 1
                continue
        
        # Final summary with detailed counts
        print(f"\\n=== NORMALIZATION COMPLETED ===")
        print(f"Total documents in source: {{total_docs}}")
        print(f"Successfully processed: {{processed}}")
        print(f"Errors encountered: {{errors}}")
        print(f"Skipped documents: {{skipped}}")
        
        # Verify target collection has data
        try:
            target_count = target_col.count_documents({{}})
            print(f"Documents in target collection: {{target_count}}")
            
            if target_count == 0:
                print("⚠️  WARNING: No documents were written to target collection!")
                print("This may indicate a processing issue or empty source data.")
            elif target_count != processed:
                print(f"⚠️  WARNING: Document count mismatch! Expected {{processed}}, found {{target_count}}")
            else:
                print("[SUCCESS] Document count verification successful")
                
        except Exception as verify_error:
            print(f"❌ Error verifying target collection: {{verify_error}}")
        
        print(f"Normalized data saved to {{TARGET_DB}}.{{TARGET_COLL}}")
        
        # Create indexes for better performance
        try:
            target_col.create_index("statute_name")  # Use normalized field name
            target_col.create_index("year")          # Use normalized field name
            target_col.create_index("section_number") # Use normalized field name
            print("[SUCCESS] Created indexes for efficient querying")
        except Exception as index_error:
            print(f"⚠️  Error creating indexes: {{index_error}}")
        
    except Exception as e:
        print(f"❌ Error during normalization: {{str(e)}}")
        print(f"Error type: {{type(e).__name__}}")
        import traceback
        print(f"Traceback: {{traceback.format_exc()}}")
        raise e
    finally:
        if 'client' in locals():
            client.close()
            print("✅ MongoDB connection closed")

if __name__ == "__main__":
    main()
'''
        return script
    
    @staticmethod
    def generate_structure_cleaner(config: Dict[str, Any]) -> str:
        """Generate Python script for database structure cleaning"""
        script = f'''
# -*- coding: utf-8 -*-
import pymongo
import re
from datetime import datetime
from typing import Dict, Any

# Configuration - Updated collection names
MONGO_URI = "{config.get('mongo_uri', MONGODB_URI)}"
SOURCE_DB = "{config.get('source_db', DEFAULT_DATABASE_NAME)}"
SOURCE_COLL = "{config.get('source_collection', DEFAULT_TARGET_COLLECTION)}"
TARGET_DB = "{config.get('target_db', DEFAULT_DATABASE_NAME)}"
TARGET_COLL = "{config.get('target_collection', DEFAULT_CLEANED_COLLECTION)}"

def clean_document_structure(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Clean and standardize document structure with enhanced field mapping"""
    cleaned_doc = {{}}
    
    # Enhanced field mappings based on actual schema
    field_mappings = {{
        'Statute_Name': 'statute_name',
        'Act_Ordinance': 'act_ordinance',
        'Year': 'year',
        'Date': 'date',
        'Promulgation_Date': 'promulgation_date',
        'Section': 'section',
        'Section_Number': 'section_number',
        'Section_Definition': 'section_definition',
        'Definition': 'definition',
        'Category': 'category',
        'Source': 'source',
        'Province': 'province',
        'Statute_Type': 'statute_type',
        'Bookmark_ID': 'bookmark_id',
        'PDF_URL': 'pdf_url',
        'Blob_Url': 'blob_url',
        'Statute_Content': 'content',
        'Statute_HTML': 'html_content',
        'Statute_RAG_Content': 'rag_content',
        'Citations': 'citations',
        'Textual_Metadata': 'textual_metadata'
    }}
    
    # Map and clean fields
    for old_field, new_field in field_mappings.items():
        if old_field in doc:
            value = doc[old_field]
            if value is not None and value != "":
                # Clean string values
                if isinstance(value, str):
                    value = value.strip()
                    if value:
                        cleaned_doc[new_field] = value
                else:
                    cleaned_doc[new_field] = value
    
    # Handle special fields
    if 'original_id' in doc:
        cleaned_doc['original_id'] = doc['original_id']
    
    if 'normalized_at' in doc:
        cleaned_doc['normalized_at'] = doc['normalized_at']
    
    if 'normalization_version' in doc:
        cleaned_doc['normalization_version'] = doc['normalization_version']
    
    # Add metadata
    cleaned_doc['cleaned_at'] = datetime.now()
    cleaned_doc['cleaning_version'] = "2.0"
    
    return cleaned_doc

def main():
    try:
        client = pymongo.MongoClient(MONGO_URI)
        source_col = client[SOURCE_DB][SOURCE_COLL]
        target_col = client[TARGET_DB][TARGET_COLL]
        
        # Clear target collection
        target_col.delete_many({{}})
        
        # Process documents
        total_docs = source_col.count_documents({{}})
        processed = 0
        
        print(f"Starting enhanced structure cleaning of {{total_docs}} documents...")
        print(f"Source: {{SOURCE_DB}}.{{SOURCE_COLL}}")
        print(f"Target: {{TARGET_DB}}.{{TARGET_COLL}}")
        
        for doc in source_col.find():
            cleaned_doc = clean_document_structure(doc)
            target_col.insert_one(cleaned_doc)
            processed += 1
            
            if processed % 100 == 0:
                print(f"Cleaned {{processed}}/{{total_docs}} documents...")
        
        print(f"[SUCCESS] Successfully cleaned {{processed}} documents")
        print(f"Cleaned data saved to {{TARGET_DB}}.{{TARGET_COLL}}")
        
        # Create indexes for better performance
        target_col.create_index("statute_name")
        target_col.create_index("year")
        target_col.create_index("section_number")
        print("[SUCCESS] Created indexes for efficient querying")
        
    except Exception as e:
        print(f"❌ Error during structure cleaning: {{str(e)}}")
        raise e
    finally:
        client.close()

if __name__ == "__main__":
    main()
'''
        return script
    
    @staticmethod
    def generate_alphabetical_sorter(config: Dict[str, Any]) -> str:
        """Generate Python script for alphabetical sorting with enhanced logic"""
        script = f'''
# -*- coding: utf-8 -*-
import pymongo
from datetime import datetime
from typing import Dict, Any, List

# Configuration - Updated collection names
MONGO_URI = "{config.get('mongo_uri', MONGODB_URI)}"
SOURCE_DB = "{config.get('source_db', DEFAULT_DATABASE_NAME)}"
SOURCE_COLL = "{config.get('source_collection', DEFAULT_CLEANED_COLLECTION)}"
TARGET_DB = "{config.get('target_db', DEFAULT_DATABASE_NAME)}"
TARGET_COLL = "{config.get('target_collection', DEFAULT_SORTED_COLLECTION)}"

def extract_sort_key(statute_name: str) -> str:
    """Extract sort key from statute name with enhanced logic"""
    if not statute_name:
        return "zzz_unknown"
    
    # Remove common prefixes for better sorting
    name = statute_name.strip()
    
    # Handle numeric prefixes (keep them for proper ordering)
    if name and name[0].isdigit():
        return name
    
    # Remove common legal prefixes
    prefixes_to_remove = [
        "The ", "An ", "A ", "Act ", "Regulation ", "Ordinance "
    ]
    
    for prefix in prefixes_to_remove:
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    
    return name.strip()

def create_sort_order(documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Create sort order with enhanced logic"""
    # Sort by statute name first
    sorted_by_name = sorted(documents, key=lambda x: extract_sort_key(x.get('statute_name', '')))
    
    # Then sort by year if available
    def year_sort_key(doc):
        year = doc.get('year')
        if year is None:
            return 9999  # Put documents without year at the end
        try:
            return int(year)
        except (ValueError, TypeError):
            return 9999
    
    # Sort by year within each name group
    final_sorted = []
    current_name = None
    current_group = []
    
    for doc in sorted_by_name:
        doc_name = doc.get('statute_name', '')
        
        if doc_name != current_name:
            # Sort the current group by year and add to final list
            if current_group:
                year_sorted = sorted(current_group, key=year_sort_key)
                final_sorted.extend(year_sorted)
            
            # Start new group
            current_name = doc_name
            current_group = [doc]
        else:
            current_group.append(doc)
    
    # Don't forget the last group
    if current_group:
        year_sorted = sorted(current_group, key=year_sort_key)
        final_sorted.extend(year_sorted)
    
    return final_sorted

def main():
    try:
        client = pymongo.MongoClient(MONGO_URI)
        source_col = client[SOURCE_DB][SOURCE_COLL]
        target_col = client[TARGET_DB][TARGET_COLL]
        
        # Clear target collection
        target_col.delete_many({{}})
        
        # Get all documents and sort them
        documents = list(source_col.find())
        total_docs = len(documents)
        
        print(f"Starting enhanced alphabetical sorting of {{total_docs}} documents...")
        print(f"Source: {{SOURCE_DB}}.{{SOURCE_COLL}}")
        print(f"Target: {{TARGET_DB}}.{{TARGET_COLL}}")
        
        # Sort documents with enhanced logic
        sorted_docs = create_sort_order(documents)
        
        # Insert sorted documents with order index
        for index, doc in enumerate(sorted_docs):
            doc['sort_order'] = index + 1
            doc['sorted_at'] = datetime.now()
            doc['sorting_version'] = "2.0"
            target_col.insert_one(doc)
            
            if (index + 1) % 100 == 0:
                print(f"Sorted {{index + 1}}/{{total_docs}} documents...")
        
        print(f"[SUCCESS] Successfully sorted {{total_docs}} documents")
        print(f"Sorted data saved to {{TARGET_DB}}.{{TARGET_COLL}}")
        
        # Create indexes for efficient sorting and querying
        target_col.create_index("sort_order")
        target_col.create_index("statute_name")
        target_col.create_index("year")
        target_col.create_index([("statute_name", 1), ("year", 1)])
        print("[SUCCESS] Created indexes for efficient querying")
        
    except Exception as e:
        print(f"❌ Error during sorting: {{str(e)}}")
        raise e
    finally:
        client.close()

if __name__ == "__main__":
    main()
'''
        return script

class ScriptExecutor:
    """Executes generated Python scripts"""
    
    @staticmethod
    async def execute_script(script_content: str, script_name: str) -> Dict[str, Any]:
        """Execute a Python script and return results"""
        try:
            # Create temporary script file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(script_content)
                script_path = f.name
            
            # Get the current Python executable and environment
            import sys
            python_executable = sys.executable
            
            # Set up environment variables
            env = os.environ.copy()
            
            # Add the backend directory to PYTHONPATH to ensure packages are found
            backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(script_path))))
            env['PYTHONPATH'] = os.pathsep.join([
                backend_dir,
                os.path.dirname(backend_dir),  # Project root
                env.get('PYTHONPATH', '')
            ])
            
            print(f"Executing script: {script_name}")
            print(f"Python executable: {python_executable}")
            print(f"Script path: {script_path}")
            print(f"Backend directory: {backend_dir}")
            print(f"PYTHONPATH: {env['PYTHONPATH']}")
            
            # Execute script with better error handling and encoding
            result = subprocess.run(
                [python_executable, script_path],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=600,  # 10 minute timeout for large datasets
                env=env,
                cwd=backend_dir  # Set working directory to backend
            )
            
            # Clean up
            os.unlink(script_path)
            
            # Enhanced result processing
            success = result.returncode == 0
            stdout = result.stdout.strip() if result.stdout else ""
            stderr = result.stderr.strip() if result.stderr else ""
            
            # Check for common Python errors in stderr
            if stderr and any(error in stderr.lower() for error in ['import error', 'module not found', 'syntax error']):
                success = False
            
            # Log the execution details for debugging
            print(f"Script {script_name} execution completed:")
            print(f"  Return code: {result.returncode}")
            print(f"  Success: {success}")
            print(f"  Stdout length: {len(stdout)}")
            print(f"  Stderr length: {len(stderr)}")
            if stdout:
                print(f"  Stdout preview: {stdout[:500]}...")
            if stderr:
                print(f"  Stderr content: {stderr}")
            
            return {
                'success': success,
                'script_name': script_name,
                'stdout': stdout,
                'stderr': stderr,
                'return_code': result.returncode,
                'executed_at': datetime.now(timezone.utc).isoformat()
            }
            
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'script_name': script_name,
                'error': 'Script execution timed out after 10 minutes',
                'executed_at': datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            return {
                'success': False,
                'script_name': script_name,
                'error': str(e),
                'executed_at': datetime.now(timezone.utc).isoformat()
            }

# Helper function for section sorting (replicating CLI script logic)
def section_sort_key(section):
    """
    Returns a tuple for sorting sections:
    - (0, '') for preamble (always first)
    - (1, numeric value) for numeric sections
    - (2, lowercase string) for non-numeric sections
    """
    num = section.get("number", "")
    if isinstance(num, str) and num.strip().lower() == "preamble":
        return (0, "")
    
    # Try to parse as int or float
    try:
        # Remove leading/trailing whitespace
        num_str = num.strip() if isinstance(num, str) else str(num)
        
        # Check if it's a digit
        if num_str.isdigit():
            n = int(num_str)
            return (1, n)
        elif num_str.replace('.', '').replace('-', '').isdigit():
            n = float(num_str)
            return (1, n)
    except (ValueError, TypeError):
        pass
    
    # Not numeric, not preamble - use lowercase string
    return (2, str(num).lower() if num else "")

# Simple normalization function for the workflow (simplified version)
def normalize_statute_name_workflow(name):
    """
    Simplified statute name normalization for the workflow.
    This is a basic version that handles the core normalization logic.
    """
    if not name:
        return "UNKNOWN"
    
    # Convert to string and strip whitespace
    name = str(name).strip()
    
    # Remove extra whitespace and newlines
    name = re.sub(r'\s+', ' ', name)
    
    # Convert to title case
    name = name.title()
    
    # Standardize common abbreviations
    name = name.replace('Act', 'Act')
    name = name.replace('Regulation', 'Regulation')
    name = name.replace('Ordinance', 'Ordinance')
    name = name.replace('Code', 'Code')
    name = name.replace('Law', 'Law')
    
    # Remove special characters but keep spaces and basic punctuation
    name = re.sub(r'[^\w\s\-\.\(\)]', '', name)
    
    # Clean up multiple spaces again
    name = re.sub(r'\s+', ' ', name).strip()
    
    return name if name else "UNKNOWN"

# API Endpoints

@router.post("/generate-scripts")
async def generate_normalization_scripts(config: Dict[str, Any]):
    """Generate normalization scripts based on configuration"""
    try:
        generator = NormalizationScriptGenerator()
        
        scripts = {
            'statute_name_normalizer': generator.generate_statute_name_normalizer(config),
            'structure_cleaner': generator.generate_structure_cleaner(config),
            'alphabetical_sorter': generator.generate_alphabetical_sorter(config)
        }
        
        return {
            "success": True,
            "message": "Scripts generated successfully",
            "scripts": scripts,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate scripts: {str(e)}"
        )

@router.post("/execute-normalization")
async def execute_normalization(
    config: NormalizationConfig = NormalizationConfig(),
    save_metadata: bool = False
):
    """
    Execute the complete normalization workflow replicating the CLI script logic.
    
    Args:
        config: Database and collection configuration
        save_metadata: Whether to save metadata as a JSON file
        
    Returns:
        Comprehensive normalization results with metadata
    """
    try:
        # Get collection names from config
        collections = get_collection_names(config)
        source_collection = collections["source"]
        target_collection = collections["target"]
        database_name = collections["database"]
        
        logger.info("🔍 Starting comprehensive database normalization process...")
        logger.info(f"📊 Source: {database_name}.{source_collection}")
        logger.info(f"📊 Target: {database_name}.{target_collection}")
        
        # Get database connection
        db = get_db()
        raw_col = db[source_collection]
        normalized_col = db[target_collection]
        
        # Check if source collection exists and has data
        available_collections = await db.list_collection_names()
        if source_collection not in available_collections:
            return {
                "success": False,
                "message": f"Source collection '{source_collection}' does not exist",
                "available_collections": available_collections
            }
        
        source_count = await raw_col.count_documents({})
        if source_count == 0:
            return {
                "success": False,
                "message": f"Source collection '{source_collection}' is empty",
                "source_count": 0
            }
        
        logger.info(f"📋 Found {source_count} documents in source collection")
        
        # Clear existing normalized data
        await normalized_col.delete_many({})
        logger.info("🗑️  Cleared existing normalized collection")
        
        # Initialize metadata tracking
        metadata = {
            "total_documents_processed": 0,
            "unique_statutes": 0,
            "total_sections": 0,
            "sections_by_type": {
                "preamble": 0,
                "numeric": 0,
                "non_numeric": 0
            },
            "sorting_decisions": {
                "alphabetical_sort": 0,
                "numeric_sort": 0
            },
            "statute_details": [],
            "normalized_names": {},
            "processing_start": datetime.now(timezone.utc).isoformat(),
            "script_version": "2.0",
            "db_name": database_name,
            "source_collection": source_collection,
            "target_collection": target_collection,
            "configuration_used": {
                "source_collection": config.source_collection,
                "target_collection": config.target_collection,
                "database_name": config.database_name,
                "cleaned_collection": config.cleaned_collection,
                "sorted_collection": config.sorted_collection
            }
        }
        
        # Group sections by normalized Statute_Name
        statute_dict = {}
        logger.info("📋 Processing documents and grouping by statute name...")
        
        async for doc in raw_col.find({}):
            metadata["total_documents_processed"] += 1
            original_name = doc.get(get_source_field("STATUTE_NAME"), "UNKNOWN")
            
            # Use the workflow normalization function
            normalized_name = normalize_statute_name_workflow(original_name)
            
            # Track name normalization
            if original_name != normalized_name:
                metadata["normalized_names"][original_name] = normalized_name
            
            # Remove fields you don't want in the section
            section = {k: v for k, v in doc.items() if k not in [get_source_field("STATUTE_NAME"), "_id"]}
            
            if normalized_name not in statute_dict:
                statute_dict[normalized_name] = []
            statute_dict[normalized_name].append(section)
            
            # Log progress every 1000 documents
            if metadata["total_documents_processed"] % 1000 == 0:
                logger.info(f"📋 Processed {metadata['total_documents_processed']}/{source_count} documents...")
        
        logger.info(f"📋 Processed {metadata['total_documents_processed']} documents")
        logger.info(f"📋 Found {len(statute_dict)} unique statutes")
        
        # Build normalized list and insert into MongoDB
        normalized_docs = []
        logger.info("🔧 Building normalized documents with sorted sections...")
        
        for statute_name, sections in statute_dict.items():
            metadata["unique_statutes"] += 1
            metadata["total_sections"] += len(sections)
            
            # Track section types
            for section in sections:
                num = section.get("number", "")
                if isinstance(num, str) and num.strip().lower() == "preamble":
                    metadata["sections_by_type"]["preamble"] += 1
                else:
                    try:
                        float(num)
                        metadata["sections_by_type"]["numeric"] += 1
                    except (ValueError, TypeError):
                        metadata["sections_by_type"]["non_numeric"] += 1
            
            statute_detail = {
                "statute_name": statute_name,
                "section_count": len(sections),
                "section_numbers": [s.get("number", "") for s in sections],
                "sorting_method": "unknown"
            }
            
            # Sort sections using the same logic as CLI script
            if len(sections) <= 2:
                # Check if all section numbers are non-numeric (except preamble)
                non_numeric = []
                for s in sections:
                    num = s.get("number", "")
                    if isinstance(num, str) and num.strip().lower() == "preamble":
                        continue
                    try:
                        float(num)
                    except (ValueError, TypeError):
                        non_numeric.append(s)
                
                # If all non-preamble sections are non-numeric, sort alphabetically (preamble first)
                preamble_count = sum(1 for s in sections if isinstance(s.get("number", ""), str) and s.get("number", "").strip().lower() == "preamble")
                if len(non_numeric) == (len(sections) - preamble_count):
                    sections = sorted(sections, key=section_sort_key)
                    metadata["sorting_decisions"]["alphabetical_sort"] += 1
                    statute_detail["sorting_method"] = "alphabetical"
                else:
                    sections = sorted(sections, key=section_sort_key)
                    metadata["sorting_decisions"]["numeric_sort"] += 1
                    statute_detail["sorting_method"] = "numeric"
            else:
                # For more than 2 sections, always use the sort key (preamble first, then numeric, then text)
                sections = sorted(sections, key=section_sort_key)
                metadata["sorting_decisions"]["numeric_sort"] += 1
                statute_detail["sorting_method"] = "numeric"
            
            metadata["statute_details"].append(statute_detail)
            
            normalized_docs.append({
                "Statute_Name": statute_name,
                "Sections": sections
            })
        
        # Sort statutes alphabetically by name
        normalized_docs.sort(key=lambda x: x["Statute_Name"].lower())
        
        # Insert into MongoDB
        if normalized_docs:
            result = await normalized_col.insert_many(normalized_docs)
            logger.info(f"✅ Inserted {len(normalized_docs)} normalized statutes into {database_name}.{target_collection}")
            logger.info(f"✅ Inserted document IDs: {[str(id) for id in result.inserted_ids[:5]]}...")
        else:
            logger.warning("⚠️  No normalized documents to insert")
        
        # Create index on Statute_Name for faster queries
        try:
            await normalized_col.create_index("Statute_Name")
            logger.info("📊 Created index on Statute_Name field")
        except Exception as index_error:
            logger.warning(f"⚠️  Error creating index: {index_error}")
        
        # Final metadata calculations
        metadata["processing_end"] = datetime.now(timezone.utc).isoformat()
        metadata["processing_duration_seconds"] = (datetime.fromisoformat(metadata["processing_end"].replace('Z', '+00:00')) - 
                                                 datetime.fromisoformat(metadata["processing_start"].replace('Z', '+00:00'))).total_seconds()
        
        if metadata["unique_statutes"] > 0:
            metadata["average_sections_per_statute"] = round(metadata["total_sections"] / metadata["unique_statutes"], 2)
        
        # Save metadata to file if requested
        if save_metadata:
            try:
                metadata_dir = "metadata"
                os.makedirs(metadata_dir, exist_ok=True)
                meta_filename = f"metadata_normalize_structure_{database_name}_{target_collection}_{datetime.now().date().isoformat()}.json"
                meta_path = os.path.join(metadata_dir, meta_filename)
                
                with open(meta_path, "w", encoding="utf-8") as f:
                    json.dump(metadata, f, ensure_ascii=False, indent=2)
                
                logger.info(f"📊 Metadata saved to {meta_path}")
                metadata["metadata_file_saved"] = True
                metadata["metadata_file_path"] = meta_path
            except Exception as save_error:
                logger.error(f"❌ Error saving metadata file: {save_error}")
                metadata["metadata_file_saved"] = False
                metadata["metadata_file_error"] = str(save_error)
        else:
            metadata["metadata_file_saved"] = False
        
        # Log comprehensive metadata
        logger.info("\n📊 NORMALIZATION METADATA:")
        logger.info("=" * 50)
        logger.info(f"📋 Total documents processed: {metadata['total_documents_processed']}")
        logger.info(f"📋 Unique statutes: {metadata['unique_statutes']}")
        logger.info(f"📋 Total sections: {metadata['total_sections']}")
        if metadata["unique_statutes"] > 0:
            logger.info(f"📋 Average sections per statute: {metadata['average_sections_per_statute']}")
        
        logger.info("\n📊 Section Types:")
        logger.info(f"   - Preamble sections: {metadata['sections_by_type']['preamble']}")
        logger.info(f"   - Numeric sections: {metadata['sections_by_type']['numeric']}")
        logger.info(f"   - Non-numeric sections: {metadata['sections_by_type']['non_numeric']}")
        
        logger.info("\n📊 Sorting Decisions:")
        logger.info(f"   - Alphabetical sorting: {metadata['sorting_decisions']['alphabetical_sort']} statutes")
        logger.info(f"   - Numeric sorting: {metadata['sorting_decisions']['numeric_sort']} statutes")
        
        logger.info(f"\n📊 Name Normalizations: {len(metadata['normalized_names'])}")
        if metadata["normalized_names"]:
            logger.info("   Sample normalizations:")
            for i, (original, normalized) in enumerate(list(metadata["normalized_names"].items())[:5]):
                logger.info(f"     '{original}' → '{normalized}'")
        
        return {
            "success": True,
            "message": "Comprehensive normalization completed successfully",
            "metadata": metadata,
            "summary": {
                "total_documents_processed": metadata["total_documents_processed"],
                "unique_statutes": metadata["unique_statutes"],
                "total_sections": metadata["total_sections"],
                "average_sections_per_statute": metadata.get("average_sections_per_statute", 0),
                "sections_by_type": metadata["sections_by_type"],
                "sorting_decisions": metadata["sorting_decisions"],
                "name_normalizations_count": len(metadata["normalized_names"]),
                "metadata_file_saved": metadata.get("metadata_file_saved", False),
                "metadata_file_path": metadata.get("metadata_file_path", None)
            },
            "completed_at": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Comprehensive normalization failed: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Comprehensive normalization failed",
                "message": str(e),
                "error_type": type(e).__name__,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )

@router.post("/preview-normalized-structure")
async def preview_normalized_structure(
    limit: int = 5,
    config: NormalizationConfig = NormalizationConfig()
):
    """
    Preview the normalized data structure showing sample statutes with their sections.
    This helps verify the normalization workflow output.
    """
    try:
        # Get collection names from config
        collections = get_collection_names(config)
        target_collection = collections["target"]
        database_name = collections["database"]
        
        db = get_db()
        normalized_col = db[target_collection]
        
        # Check if normalized collection exists and has data
        # Use the database object directly to list collections
        available_collections = await db.list_collection_names()
        if target_collection not in available_collections:
            return {
                "success": False,
                "message": f"Normalized collection '{target_collection}' does not exist",
                "available_collections": available_collections,
                "configuration_used": {
                    "source_collection": config.source_collection,
                    "target_collection": config.target_collection,
                    "database_name": config.database_name
                }
            }
        
        normalized_count = await normalized_col.count_documents({})
        if normalized_count == 0:
            return {
                "success": False,
                "message": f"Normalized collection '{target_collection}' is empty",
                "normalized_count": 0,
                "configuration_used": {
                    "source_collection": config.source_collection,
                    "target_collection": config.target_collection,
                    "database_name": config.database_name
                }
            }
        
        # Get sample documents
        sample_docs = await normalized_col.find().limit(limit).to_list(length=limit)
        
        # Format the preview data
        preview_data = []
        for doc in sample_docs:
            statute_info = {
                "statute_name": doc.get("Statute_Name", "Unknown"),
                "section_count": len(doc.get("Sections", [])),
                "sections_preview": []
            }
            
            # Show first few sections
            for i, section in enumerate(doc.get("Sections", [])[:3]):
                section_preview = {
                    "section_number": section.get("number", ""),
                    "section_type": "preamble" if str(section.get("number", "")).strip().lower() == "preamble" else "section",
                    "content_preview": str(section.get("content", section.get("definition", "")))[:100] + "..." if len(str(section.get("content", section.get("definition", "")))) > 100 else str(section.get("content", section.get("definition", "")))
                }
                statute_info["sections_preview"].append(section_preview)
            
            if len(doc.get("Sections", [])) > 3:
                statute_info["sections_preview"].append({
                    "section_number": f"... and {len(doc.get('Sections', [])) - 3} more sections",
                    "section_type": "info",
                    "content_preview": ""
                })
            
            preview_data.append(statute_info)
        
        return {
            "success": True,
            "message": f"Preview of normalized data structure (showing {len(preview_data)} of {normalized_count} statutes)",
            "total_statutes": normalized_count,
            "preview_limit": limit,
            "preview_data": preview_data,
            "data_structure": {
                "document_format": "Each document has 'Statute_Name' and 'Sections' array",
                "sections_format": "Each section has 'number', 'content', and other fields from original",
                "sorting": "Sections are sorted: preamble first, then numeric, then alphabetical",
                "normalization": "Statute names are normalized (cleaned, title case, standardized)"
            },
            "configuration_used": {
                "source_collection": config.source_collection,
                "target_collection": config.target_collection,
                "database_name": config.database_name
            },
            "previewed_at": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error previewing normalized structure: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to preview normalized structure: {str(e)}"
        )

@router.post("/normalization-status")
async def get_normalization_status(
    config: NormalizationConfig = NormalizationConfig()
):
    """Get the current status of normalization process"""
    try:
        # Get collection names from config
        collections = get_collection_names(config)
        source_collection = collections["source"]
        target_collection = collections["target"]
        database_name = collections["database"]
        
        db = get_db()
        
        # Check if normalized collections exist using configurable collection names
        available_collections = await db.list_collection_names()
        
        status_info = {
            "raw_statutes_count": 0,
            "normalized_statutes_count": 0,
            "collections_exist": {
                "raw_statutes": source_collection in available_collections,
                "normalized_statutes": target_collection in available_collections
            }
        }
        
        # Get document counts using configurable collection names
        if source_collection in available_collections:
            status_info["raw_statutes_count"] = await db[source_collection].count_documents({})
        
        if target_collection in available_collections:
            status_info["normalized_statutes_count"] = await db[target_collection].count_documents({})
        
        return {
            "success": True,
            "status": status_info,
            "configuration_used": {
                "source_collection": config.source_collection,
                "target_collection": config.target_collection,
                "database_name": config.database_name
            },
            "checked_at": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting normalization status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get normalization status: {str(e)}"
        )

@router.post("/preview-normalized")
async def preview_normalized_data(
    limit: int = 10,
    config: NormalizationConfig = NormalizationConfig()
):
    """Preview normalized data from the target collection"""
    try:
        # Get collection names from config
        collections = get_collection_names(config)
        target_collection = collections["target"]
        database_name = collections["database"]
        
        db = get_db()
        normalized_col = db[target_collection]
        
        # Check if collection exists
        available_collections = await db.list_collection_names()
        if target_collection not in available_collections:
            return {
                "success": False,
                "message": f"Normalized collection '{target_collection}' does not exist",
                "available_collections": available_collections,
                "configuration_used": {
                    "source_collection": config.source_collection,
                    "target_collection": config.target_collection,
                    "database_name": config.database_name
                }
            }
        
        # Get sample documents
        sample_docs = await normalized_col.find().limit(limit).to_list(length=limit)
        
        # Convert ObjectIds to strings for JSON serialization
        def convert_objectid(obj):
            if hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes, bytearray)):
                if isinstance(obj, dict):
                    return {k: convert_objectid(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_objectid(item) for item in obj]
            elif hasattr(obj, '__str__'):
                return str(obj)
            return obj
        
        converted_docs = convert_objectid(sample_docs)
        
        return {
            "success": True,
            "message": f"Preview of {len(converted_docs)} normalized documents",
            "data": converted_docs,
            "total_in_collection": await normalized_col.count_documents({}),
            "configuration_used": {
                "source_collection": config.source_collection,
                "target_collection": config.target_collection,
                "database_name": config.database_name
            },
            "previewed_at": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error previewing normalized data: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to preview normalized data: {str(e)}"
        )

@router.post("/rollback")
async def rollback_normalization(
    config: NormalizationConfig = NormalizationConfig()
):
    """Rollback normalization by clearing the normalized collection"""
    try:
        # Get collection names from config
        collections = get_collection_names(config)
        target_collection = collections["target"]
        database_name = collections["database"]
        
        db = get_db()
        normalized_col = db[target_collection]
        
        # Get count before deletion
        count_before = await normalized_col.count_documents({})
        
        # Clear the collection
        result = await normalized_col.delete_many({})
        
        return {
            "success": True,
            "message": f"Rollback completed successfully",
            "deleted_count": result.deleted_count,
            "count_before": count_before,
            "count_after": 0,
            "configuration_used": {
                "source_collection": config.source_collection,
                "target_collection": config.target_collection,
                "database_name": config.database_name
            },
            "rolled_back_at": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error during rollback: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Rollback failed: {str(e)}"
        )