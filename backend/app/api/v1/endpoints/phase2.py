from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any, Optional
from pydantic import BaseModel
from ....core.database import get_db
from ....core.config import settings
from ....core.services import NormalizationService
import pymongo
import tempfile
import subprocess
import os
import json
import re
from datetime import datetime, timezone
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

# New request model for service-based normalization
class NormalizationRequest(BaseModel):
    source_db: str
    target_db: str
    options: Optional[Dict[str, Any]] = None

# New models for sorting and cleaning operations
class SortingRules(BaseModel):
    preamble_first: bool = True
    numeric_order: bool = True
    alphabetical_fallback: bool = True
    custom_sort_order: Optional[Dict[str, int]] = None

class SortingRequest(BaseModel):
    rules: SortingRules
    scope: Optional[str] = "all"  # "all", "selected", or specific statute names
    target_collection: Optional[str] = None
    database_name: Optional[str] = None

class FieldMapping(BaseModel):
    source: str
    target: str
    enabled: bool = True

class CleaningRequest(BaseModel):
    mappings: list[FieldMapping]
    scope: Optional[str] = "all"  # "all", "selected", or specific statute names
    target_collection: Optional[str] = None
    database_name: Optional[str] = None

# Default MongoDB connection settings - Updated to use correct collection names
MONGODB_URI = settings.mongodb_url
DEFAULT_DATABASE_NAME = settings.mongodb_db
DEFAULT_SOURCE_COLLECTION = "raw_statutes"  # Input collection
DEFAULT_TARGET_COLLECTION = "normalized_statutes"  # Output collection
DEFAULT_CLEANED_COLLECTION = "normalized_statutes"  # Intermediate collection
DEFAULT_SORTED_COLLECTION = "sorted_statutes"  # Final collection



def get_collection_names(config: NormalizationConfig) -> Dict[str, str]:
    """Get collection names from config or defaults"""
    return {
        "source": config.source_collection or DEFAULT_SOURCE_COLLECTION,
        "target": config.target_collection or DEFAULT_TARGET_COLLECTION,
        "cleaned": config.cleaned_collection or DEFAULT_CLEANED_COLLECTION,
        "sorted": config.sorted_collection or DEFAULT_SORTED_COLLECTION,
        "database": config.database_name or DEFAULT_DATABASE_NAME
    }

async def _get_db_client():
    """Return (is_async, db) where is_async True if motor AsyncIOMotorDatabase is used, else False and pymongo Database."""
    db = get_db()
    if db is not None:
        return True, db
    # fallback to pymongo for test scenarios
    client = pymongo.MongoClient(settings.mongodb_url)
    return False, client[settings.mongodb_db]

class NormalizationScriptGenerator:
    """Generates Python scripts for database normalization"""

    @staticmethod
    def generate_statute_name_normalizer(config: Dict[str, Any]) -> str:
        """Generate Python script for statute name normalization using a safe token template."""
        template = '''
# -*- coding: utf-8 -*-
import sys
import os
import re
from datetime import datetime
from typing import Dict, Any

try:
    import pymongo
    print("[SUCCESS] pymongo imported successfully")
except ImportError as e:
    print(f"❌ Failed to import pymongo: {e}")
    print(f"Python executable: {sys.executable}")
    print(f"Python path: {sys.path}")
    print(f"Current working directory: {os.getcwd()}")
    sys.exit(1)

# Configuration tokens (will be replaced by the generator)
MONGO_URI = "__MONGO_URI__"
SOURCE_DB = "__SOURCE_DB__"
SOURCE_COLL = "__SOURCE_COLL__"
TARGET_DB = "__TARGET_DB__"
TARGET_COLL = "__TARGET_COLL__"

FIELD_NAMES = {
    "STATUTE_NAME": "Statute_Name",
    "ACT_ORDINANCE": "Act_Ordinance",
    "SECTION": "Section",
    "YEAR": "Year",
    "DATE": "Date",
    "STATUTE": "Statute",
    "STATUTE_HTML": "Statute_HTML",
    "STATUTE_RAG_CONTENT": "Statute_RAG_Content",
    "statute_name": "statute_name",
    "act_ordinance": "act_ordinance",
    "section_number": "section_number",
    "section_definition": "section_definition",
    "year": "year",
    "date": "date",
    "statute_content": "statute_content",
    "statute_html": "statute_html",
    "statute_rag_content": "statute_rag_content",
    "normalized_at": "normalized_at",
    "normalization_version": "normalization_version",
    "original_id": "original_id"
}

def get_source_field(field_key: str) -> str:
    return FIELD_NAMES.get(field_key, field_key)

def get_normalized_field(field_key: str) -> str:
    return FIELD_NAMES.get(field_key, field_key)

def normalize_statute_name(name: str) -> str:
    if not name:
        return "UNKNOWN"
    name = str(name).strip()
    name = re.sub(r'\\s+', ' ', name)
    prefixes_to_remove = ["The ", "An ", "A "]
    for prefix in prefixes_to_remove:
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    name = name.title()
    name = name.replace('Act', 'Act')
    name = name.replace('Regulation', 'Regulation')
    name = name.replace('Ordinance', 'Ordinance')
    name = re.sub(r'[^\\w\\s\\-\\.\\(\\)]', '', name)
    name = re.sub(r'\\s+', ' ', name).strip()
    return name if name else "UNKNOWN"

def extract_section_info(section_text: str):
    if not section_text:
        return {"section_number": "", "definition": ""}
    section_text = str(section_text).strip()
    section_match = re.search(r'(?:Section\\s*)?(\\d+)(?:\\.|\\s|$)', section_text)
    section_number = section_match.group(1) if section_match else ""
    if section_match:
        definition = section_text[section_match.end():].strip()
        definition = re.sub(r'^[\\s\\-\\.]+', '', definition)
    else:
        definition = section_text
    return {"section_number": section_number, "definition": definition}

def normalize_document(doc: Dict[str, Any]) -> Dict[str, Any]:
    normalized_doc = doc.copy()
    statute_name_field = get_source_field("STATUTE_NAME")
    if statute_name_field in doc:
        normalized_doc[get_normalized_field("statute_name")] = normalize_statute_name(doc[statute_name_field])
    act_ordinance_field = get_source_field("ACT_ORDINANCE")
    if act_ordinance_field in doc:
        normalized_doc[get_normalized_field("act_ordinance")] = normalize_statute_name(doc[act_ordinance_field])
    section_field = get_source_field("SECTION")
    if section_field in doc:
        section_info = extract_section_info(doc[section_field])
        normalized_doc[get_normalized_field("section_number")] = section_info['section_number']
        normalized_doc[get_normalized_field("section_definition")] = section_info['definition']
    year_field = get_source_field("YEAR")
    if year_field in doc and doc[year_field]:
        try:
            year = int(doc[year_field])
            if 1900 <= year <= 2100:
                normalized_doc[get_normalized_field("year")] = year
            else:
                normalized_doc[get_normalized_field("year")] = None
        except (ValueError, TypeError):
            normalized_doc[get_normalized_field("year")] = None
    date_field = get_source_field("DATE")
    if date_field in doc and doc[date_field]:
        normalized_doc[get_normalized_field("date")] = str(doc[date_field]).strip()
    return normalized_doc

def main():
    try:
        import pymongo as _pymongo
        client = _pymongo.MongoClient(MONGO_URI)
        source_col = client[SOURCE_DB][SOURCE_COLL]
        target_col = client[TARGET_DB][TARGET_COLL]
        total_docs = source_col.count_documents({})
        processed = 0
        print(f"Starting enhanced normalization of {total_docs} documents...")
        print(f"Processing documents from {SOURCE_COLL} to {TARGET_COLL}...")
        for doc in source_col.find():
            try:
                doc_id = doc.get('_id', 'unknown')
                print(f"Processing document {doc_id}...")
                normalized = normalize_document(doc)
                result = target_col.insert_one(normalized)
                processed += 1
                if processed % 10 == 0:
                    print(f"Progress: {processed}/{total_docs} documents processed...")
            except Exception as doc_error:
                print(f"❌ Error processing document {doc.get('_id', 'unknown')}: {str(doc_error)}")
                continue
        print("\n=== NORMALIZATION COMPLETED ===")
        print(f"Total documents in source: {total_docs}")
        print(f"Successfully processed: {processed}")
    except Exception as e:
        print(f"❌ Error during normalization: {str(e)}")
        import traceback
        print(traceback.format_exc())
        raise
    finally:
        if 'client' in locals():
            client.close()
            print("✅ MongoDB connection closed")

        # Replace tokens safely
        script = template.replace('__MONGO_URI__', str(config.get('mongo_uri', MONGODB_URI)))
        script = script.replace('__SOURCE_DB__', str(config.get('source_db', DEFAULT_DATABASE_NAME)))
        script = script.replace('__SOURCE_COLL__', str(config.get('source_collection', DEFAULT_SOURCE_COLLECTION)))
        script = script.replace('__TARGET_DB__', str(config.get('target_db', DEFAULT_DATABASE_NAME)))
        script = script.replace('__TARGET_COLL__', str(config.get('target_collection', DEFAULT_TARGET_COLLECTION)))
        return script

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
    
        # Now paginate the filtered docs
        filtered_count = len(all_docs)
        total_sections_count = sum(len(doc.get("Sections", [])) for doc in all_docs)
        sample_docs = all_docs[skip:skip+limit]

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
            "search": search,
            "preview_data": preview_data,
            "pagination": {
                "current_page": (skip // limit) + 1,
                "total_pages": (filtered_count + limit - 1) // limit,
                "has_next": skip + limit < filtered_count,
                "has_previous": skip > 0
            },
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
        # Replace tokens safely
        script = template.replace('__MONGO_URI__', str(config.get('mongo_uri', MONGODB_URI)))
        script = script.replace('__SOURCE_DB__', str(config.get('source_db', DEFAULT_DATABASE_NAME)))
        script = script.replace('__SOURCE_COLL__', str(config.get('source_collection', DEFAULT_SOURCE_COLLECTION)))
        script = script.replace('__TARGET_DB__', str(config.get('target_db', DEFAULT_DATABASE_NAME)))
        script = script.replace('__TARGET_COLL__', str(config.get('target_collection', DEFAULT_TARGET_COLLECTION)))
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

@router.post("/start-normalization")
async def start_normalization(request: NormalizationRequest):
    """
    Start normalization process using the new NormalizationService.
    
    This is a cleaner, more maintainable version of the normalization workflow.
    """
    service = None
    try:
        # Initialize service
        service = NormalizationService()
        
        # Start normalization process
        result = service.start_normalization(request.source_db, request.target_db, request.options)
        
        logger.info(f"Normalization configured: {request.source_db} → {request.target_db}")
        
        return {
            "success": True,
            "message": "Normalization process configured successfully",
            "data": result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Invalid input",
                "message": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
    except Exception as e:
        logger.error(f"Normalization service error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Normalization failed",
                "message": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
    finally:
        if service:
            service.cleanup()

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

@router.post("/execute-normalization-legacy")
async def execute_normalization_legacy(
    config: NormalizationConfig = NormalizationConfig(),
    save_metadata: bool = False
):
    """
    DEPRECATED: Legacy monolithic normalization endpoint.
    This endpoint has been moved for backward compatibility.
    Use /start-normalization instead for new implementations.
    """
    return {
        "success": False,
        "error": "DEPRECATED_ENDPOINT",
        "message": "This endpoint has been deprecated. Use /start-normalization instead.",
        "migration_guide": {
            "old_endpoint": "/execute-normalization",
            "new_endpoint": "/start-normalization",
            "status": "The new endpoint provides better performance and service architecture"
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@router.post("/execute-normalization")
async def execute_normalization(
    config: NormalizationConfig = NormalizationConfig(),
    save_metadata: bool = False
):
    """
    Execute the complete normalization workflow using the NormalizationService.
    
    This endpoint maintains backward compatibility while delegating to the modern
    service-based architecture for better performance and maintainability.
    
    Args:
        config: Database and collection configuration
        save_metadata: Whether to save metadata as a JSON file
        
    Returns:
        Comprehensive normalization results with metadata
    """
    try:
        logger.info("🔄 Executing normalization via service delegation...")
        
        # Convert legacy config to service request format
        # Note: Legacy endpoint uses same database with different collections
        # Service expects different databases, so we'll use collection names as DB identifiers
        database_name = config.database_name or DEFAULT_DATABASE_NAME
        request = NormalizationRequest(
            source_db=f"{database_name}_{config.source_collection}",  # Unique identifier for source
            target_db=f"{database_name}_{config.target_collection}",  # Unique identifier for target
            options={
                "actual_database": database_name,  # The real database name to use
                "source_collection": config.source_collection,
                "target_collection": config.target_collection,
                "cleaned_collection": config.cleaned_collection,
                "sorted_collection": config.sorted_collection,
                "save_metadata": save_metadata,
                "batch_size": 1000,  # Default batch size
                "legacy_compatibility": True,
                "same_database_mode": True  # Flag to indicate same DB, different collections
            }
        )
        
        # Use the NormalizationService
        service = NormalizationService()
        result = service.start_normalization(request.source_db, request.target_db, request.options)
        
        # Transform service result to match legacy response format for backward compatibility
        legacy_response = {
            "success": result.get("success", True),
            "message": result.get("message", "Normalization completed via service"),
            "metadata": {
                "processing_start": result.get("timestamp"),
                "script_version": "3.0-service-based",
                "service_based": True,
                "legacy_endpoint": True,
                "configuration_used": {
                    "source_collection": config.source_collection,
                    "target_collection": config.target_collection,
                    "database_name": config.database_name,
                    "cleaned_collection": config.cleaned_collection,
                    "sorted_collection": config.sorted_collection
                },
                "service_result": result.get("data", {}),
                "migration_note": "This endpoint now uses NormalizationService internally for better performance"
            },
            "summary": {
                "service_status": result.get("data", {}).get("status", "completed"),
                "service_validation": result.get("data", {}).get("validation", {}),
                "service_config": result.get("data", {}).get("config", {}),
                "modernization_note": "Consider migrating to /start-normalization for enhanced features"
            },
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "recommendation": "Use /start-normalization endpoint for new implementations"
        }
        
        logger.info("✅ Legacy normalization completed via service delegation")
        return legacy_response
        
    except Exception as e:
        logger.error(f"❌ Service-based normalization failed: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Service-based normalization failed",
                "message": str(e),
                "error_type": type(e).__name__,
                "service_based": True,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )


@router.post("/preview-normalized-structure")
async def preview_normalized_structure(
    limit: int = 100,
    skip: int = 0,
    search: str = "",
    config: NormalizationConfig = NormalizationConfig()
):
    """
    Preview the normalized data structure showing sample statutes with their sections.
    This helps verify the normalization workflow output.
    Supports pagination and search functionality.
    """
    try:
        # Get collection names from config
        collections = get_collection_names(config)
        target_collection = collections["target"]
        collections["database"]
        
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
        
        # Build search filter
        search_filter = {}
        if search.strip():
            search_filter["Statute_Name"] = {"$regex": search.strip(), "$options": "i"}

        # Add filter for 'has preamble' and 'numeric section' if requested
        filter_preamble = getattr(config, "filter_preamble", False)
        filter_numeric = getattr(config, "filter_numeric", False)
        # Compose $elemMatch for section filters
        section_elem_match = None
        if filter_preamble:
            section_elem_match = {"$or": [
                {"Section": {"$regex": "preamble", "$options": "i"}},
                {"Definition": {"$regex": "preamble", "$options": "i"}}
            ]}
        if filter_numeric:
            numeric_match = {
                "Section": {"$type": "string", "$regex": "^[0-9]+$", "$options": ""}
            }
            if section_elem_match:
                section_elem_match = {"$and": [section_elem_match, numeric_match]}
            else:
                section_elem_match = numeric_match
        if section_elem_match:
            search_filter["Sections"] = {"$elemMatch": section_elem_match}
        
        # Get total count for filtered results
        total_filtered_count = await normalized_col.count_documents(search_filter)
        
        # Get all matching documents (no pagination yet)
        all_docs = await normalized_col.find(search_filter).to_list(length=None)

        # Python-side filtering for section filters
        def section_matches(section):
            matches_preamble = False
            matches_numeric = False
            if filter_preamble:
                s_val = str(section.get("Section", "")).lower()
                d_val = str(section.get("Definition", "")).lower()
                matches_preamble = "preamble" in s_val or "preamble" in d_val
            if filter_numeric:
                s_val = str(section.get("Section", ""))
                matches_numeric = s_val.isdigit()
            if filter_preamble and filter_numeric:
                return matches_preamble and matches_numeric
            elif filter_preamble:
                return matches_preamble
            elif filter_numeric:
                return matches_numeric
            else:
                return True

        # Filter statutes by sections
        if filter_preamble or filter_numeric:
            filtered_docs = []
            for doc in all_docs:
                filtered_sections = [s for s in doc.get("Sections", []) if section_matches(s)]
                if filtered_sections:
                    doc["Sections"] = filtered_sections
                    filtered_docs.append(doc)
            all_docs = filtered_docs

        filtered_count = len(all_docs)
        total_sections_count = sum(len(doc.get("Sections", [])) for doc in all_docs)
        sample_docs = all_docs[skip:skip+limit]

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
                    "section_number": f"... and {len(doc.get("Sections", [])) - 3} more sections",
                    "section_type": "info",
                    "content_preview": ""
                })
            preview_data.append(statute_info)

        return {
            "success": True,
            "message": f"Preview of normalized data structure (showing {len(preview_data)} of {filtered_count} statutes{' matching search' if search.strip() else ''})",
            "total_statutes": normalized_count,
            "filtered_count": filtered_count,
            "total_sections": total_sections_count,
            "preview_limit": limit,
            "skip": skip,
            "search": search,
            "preview_data": preview_data,
            "pagination": {
                "current_page": (skip // limit) + 1,
                "total_pages": (filtered_count + limit - 1) // limit,
                "has_next": skip + limit < filtered_count,
                "has_previous": skip > 0
            },
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


@router.post("/preview-source-normalization")
async def preview_source_normalization(
    limit: int = 5,
    config: NormalizationConfig = NormalizationConfig()
):
    """
    Preview what the normalization will do using source data.
    This shows a simulation of the normalization process before running it.
    """
    try:
        # Get collection names from config
        collections = get_collection_names(config)
        source_collection = collections["source"]
        
        db = get_db()
        source_col = db[source_collection]
        
        # Check if source collection exists
        available_collections = await db.list_collection_names()
        if source_collection not in available_collections:
            return {
                "success": False,
                "message": f"Source collection '{source_collection}' does not exist",
                "available_collections": available_collections
            }
        
        source_count = await source_col.count_documents({})
        if source_count == 0:
            return {
                "success": False,
                "message": f"Source collection '{source_collection}' is empty"
            }
        
        # Get sample raw documents
        raw_docs = await source_col.find().limit(limit * 10).to_list(length=None)
        
        # Simulate normalization process
        def normalize_statute_name(name):
            """Simple statute name normalization for preview"""
            if not name:
                return "Unknown"
            # Basic normalization: title case, strip whitespace
            return ' '.join(name.strip().split()).title()
        
        # Group by statute name (simulate normalization)
        statute_groups = {}
        for doc in raw_docs:
            statute_name = doc.get("Statute_Name", "Unknown")
            # Apply basic name normalization
            normalized_name = normalize_statute_name(statute_name)
            
            if normalized_name not in statute_groups:
                statute_groups[normalized_name] = []
            statute_groups[normalized_name].append(doc)
        
        # Take sample statutes
        sample_statutes = list(statute_groups.items())[:limit]
        
        preview_data = []
        for statute_name, sections in sample_statutes:
            statute_info = {
                "original_name": sections[0].get("Statute_Name", "Unknown"),
                "normalized_name": statute_name,
                "section_count": len(sections),
                "sections_preview": []
            }
            
            # Show first few sections
            for i, section in enumerate(sections[:3]):
                section_preview = {
                    "section_number": section.get("Section", ""),
                    "definition": section.get("Definition", "")[:100] + "..." if len(str(section.get("Definition", ""))) > 100 else section.get("Definition", ""),
                    "year": section.get("Year", ""),
                    "source": section.get("Source", "")
                }
                statute_info["sections_preview"].append(section_preview)
            
            if len(sections) > 3:
                statute_info["sections_preview"].append({
                    "section_number": f"... and {len(sections) - 3} more sections",
                    "definition": "",
                    "year": "",
                    "source": "info"
                })
            
            preview_data.append(statute_info)
        
        return {
            "success": True,
            "message": f"Preview of normalization simulation (showing {len(preview_data)} statutes from {len(statute_groups)} unique statutes)",
            "total_raw_documents": source_count,
            "unique_statutes_found": len(statute_groups),
            "preview_data": preview_data,
            "simulation_info": {
                "process": "Grouped raw documents by normalized statute name",
                "name_normalization": "Applied title case, whitespace cleanup, and standardization",
                "section_grouping": "All sections with same statute name grouped together"
            },
            "configuration_used": {
                "source_collection": config.source_collection,
                "database_name": config.database_name
            },
            "previewed_at": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error previewing source normalization: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to preview source normalization: {str(e)}"
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
        collections["database"]
        
        is_async, db = await _get_db_client()
        # Check if normalized collections exist using configurable collection names
        if is_async:
            available_collections = await db.list_collection_names()
        else:
            available_collections = db.list_collection_names()
        
        status_info = {
            "raw_count": 0,
            "normalized_count": 0,
            "unique_statutes": 0,
            "collections_exist": {
                "raw_statutes": source_collection in available_collections,
                "normalized_statutes": target_collection in available_collections
            }
        }
        
        # Get document counts using configurable collection names
        if source_collection in available_collections:
            if is_async:
                status_info["raw_count"] = await db[source_collection].count_documents({})
            else:
                status_info["raw_count"] = db[source_collection].count_documents({})
        
        if target_collection in available_collections:
            # Get all normalized docs for true totals
            if is_async:
                normalized_docs = await db[target_collection].find({}).to_list(length=None)
            else:
                normalized_docs = list(db[target_collection].find({}))
            total_statutes = len(normalized_docs)
            total_sections = sum(len(doc.get("Sections", [])) for doc in normalized_docs)
            status_info["normalized_count"] = total_statutes
            status_info["unique_statutes"] = total_statutes
            status_info["total_statutes_processed"] = total_statutes
            status_info["total_sections_processed"] = total_sections

        return status_info
        
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
        collections["database"]
        
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
        collections["database"]
        
        db = get_db()
        normalized_col = db[target_collection]
        
        # Get count before deletion
        count_before = await normalized_col.count_documents({})
        
        # Clear the collection
        result = await normalized_col.delete_many({})
        
        return {
            "success": True,
            "message": "Rollback completed successfully",
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

@router.post("/detailed-normalized-structure")
async def get_detailed_normalized_structure(
    limit: int = 100,
    skip: int = 0,
    search: str = "",
    config: NormalizationConfig = NormalizationConfig()
):
    """
    Get detailed normalized data structure with complete section information.
    This includes all section fields like 'section', 'definition', 'Statute', etc.
    
    Parameters:
    - limit: Number of statutes to return (default: 100)
    - skip: Number of statutes to skip for pagination (default: 0)
    - search: Search term to filter statute names (default: empty)
    """
    try:
        # Get collection names from config
        collections = get_collection_names(config)
        target_collection = collections["target"]
        collections["database"]
        
        db = get_db()
        normalized_col = db[target_collection]
        
        # Check if normalized collection exists and has data
        available_collections = await db.list_collection_names()
        if target_collection not in available_collections:
            return {
                "success": False,
                "message": f"Normalized collection '{target_collection}' does not exist",
                "available_collections": available_collections
            }
        
        normalized_count = await normalized_col.count_documents({})
        if normalized_count == 0:
            return {
                "success": False,
                "message": f"Normalized collection '{target_collection}' is empty",
                "normalized_count": 0
            }
        
        # Build search filter
        search_filter = {}
        if search.strip():
            search_filter["Statute_Name"] = {"$regex": search.strip(), "$options": "i"}
        
        # Get total count for filtered results
        total_filtered_count = await normalized_col.count_documents(search_filter)
        
        # Get documents with pagination and search
        sample_docs = await normalized_col.find(search_filter).skip(skip).limit(limit).to_list(length=limit)
        
        # Format the detailed data
        detailed_data = []
        for doc in sample_docs:
            statute_info = {
                "statute_name": doc.get("Statute_Name", "Unknown"),
                "section_count": len(doc.get("Sections", [])),
                "sections": []
            }
            
            # Include all section details
            for section in doc.get("Sections", []):
                section_detail = {
                    "section": section.get("section", ""),  # Section identifier
                    "definition": section.get("definition", ""),  # Section definition/title
                    "Statute": section.get("Statute", ""),  # Full statute content
                    "number": section.get("number", ""),  # Section number
                    "content": section.get("content", ""),  # Alternative content field
                    # Include any other fields that might exist
                    "additional_fields": {
                        key: value for key, value in section.items() 
                        if key not in ["section", "definition", "Statute", "number", "content"]
                        and value is not None and str(value).strip() != ""
                    }
                }
                statute_info["sections"].append(section_detail)
            
            detailed_data.append(statute_info)
        
        return {
            "success": True,
            "message": f"Detailed normalized data structure (showing {len(detailed_data)} of {total_filtered_count} statutes{' matching search' if search.strip() else ''})",
            "total_statutes": normalized_count,
            "filtered_count": total_filtered_count,
            "limit": limit,
            "skip": skip,
            "search": search,
            "detailed_data": detailed_data,
            "pagination": {
                "current_page": (skip // limit) + 1,
                "total_pages": (total_filtered_count + limit - 1) // limit,
                "has_next": skip + limit < total_filtered_count,
                "has_previous": skip > 0
            },
            "data_structure": {
                "document_format": "Each document has 'Statute_Name' and 'Sections' array",
                "sections_format": "Each section includes: section, definition, Statute, number, content, and additional fields",
                "field_descriptions": {
                    "section": "Section identifier/name",
                    "definition": "Section definition or title",
                    "Statute": "Full statute content text",
                    "number": "Section number",
                    "content": "Alternative content field"
                }
            },
            "configuration_used": {
                "source_collection": config.source_collection,
                "target_collection": config.target_collection,
                "database_name": config.database_name
            },
            "retrieved_at": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting detailed normalized structure: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get detailed normalized structure: {str(e)}"
        )

@router.post("/apply-sorting")
async def apply_sorting(request: SortingRequest):
    """
    Apply sorting rules to normalized statute documents.
    This endpoint sorts sections within each statute according to the specified rules.
    """
    try:
        db = await get_db()
        database_name = request.database_name or DEFAULT_DATABASE_NAME
        
        # Use normalized_statutes as default source, but allow override
        source_collection_name = "normalized_statutes"
        target_collection_name = request.target_collection or "sorted_statutes"
        
        # Access the specific database and collections
        database = db[database_name]
        source_collection = database[source_collection_name]
        target_collection = database[target_collection_name]
        
        logger.info(f"Starting sorting operation from {source_collection_name} to {target_collection_name}")
        
        # Get documents to sort based on scope
        if request.scope == "all":
            cursor = source_collection.find({})
        else:
            # For now, treat any non-"all" scope as all documents
            # Future enhancement: support specific statute selection
            cursor = source_collection.find({})
        
        documents = list(cursor)
        if not documents:
            return {
                "success": False,
                "message": "No documents found to sort",
                "changes_count": 0,
                "sample_changes": []
            }
        
        logger.info(f"Found {len(documents)} documents to process")
        
        # Sort documents and track changes
        changes_count = 0
        sample_changes = []
        processed_documents = []
        
        for doc in documents:
            original_sections = doc.get("Sections", [])
            if not original_sections:
                processed_documents.append(doc)
                continue
            
            # Create custom sort key function based on rules
            def custom_sort_key(section):
                rules = request.rules
                
                if rules.custom_sort_order and isinstance(rules.custom_sort_order, dict):
                    # Use custom ordering if provided
                    section_num = section.get("number", "")
                    if str(section_num) in rules.custom_sort_order:
                        return (0, rules.custom_sort_order[str(section_num)])
                
                # Use the existing section_sort_key function
                return section_sort_key(section)
            
            # Sort sections
            sorted_sections = sorted(original_sections, key=custom_sort_key)
            
            # Check if order changed
            original_order = [s.get("number", "") for s in original_sections]
            new_order = [s.get("number", "") for s in sorted_sections]
            
            if original_order != new_order:
                changes_count += 1
                
                # Add to sample changes (limit to first 5)
                if len(sample_changes) < 5:
                    sample_changes.append({
                        "statute_name": doc.get("Statute_Name", "Unknown"),
                        "original_order": original_order[:10],  # Limit for readability
                        "new_order": new_order[:10],
                        "sections_affected": len(original_sections)
                    })
            
            # Create updated document
            updated_doc = doc.copy()
            updated_doc["Sections"] = sorted_sections
            updated_doc["sorted_at"] = datetime.now(timezone.utc).isoformat()
            updated_doc["sorting_rules_applied"] = {
                "preamble_first": request.rules.preamble_first,
                "numeric_order": request.rules.numeric_order,
                "alphabetical_fallback": request.rules.alphabetical_fallback,
                "custom_sort_order": bool(request.rules.custom_sort_order)
            }
            
            processed_documents.append(updated_doc)
        
        # Clear target collection and insert sorted documents
        await target_collection.delete_many({})
        
        if processed_documents:
            result = await target_collection.insert_many(processed_documents)
            logger.info(f"Inserted {len(result.inserted_ids)} sorted documents")
        
        return {
            "success": True,
            "message": f"Sorting applied successfully to {len(processed_documents)} documents",
            "changes_count": changes_count,
            "total_documents": len(processed_documents),
            "sample_changes": sample_changes,
            "target_collection": target_collection_name,
            "applied_at": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error applying sorting: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to apply sorting: {str(e)}"
        )

@router.post("/apply-cleaning")
async def apply_cleaning(request: CleaningRequest):
    """
    Apply field mapping and cleaning rules to normalized statute documents.
    This endpoint transforms field names and content according to the specified mappings.
    """
    try:
        db = await get_db()
        database_name = request.database_name or DEFAULT_DATABASE_NAME
        
        # Use normalized_statutes as default source, but allow override
        source_collection_name = "normalized_statutes"
        target_collection_name = request.target_collection or "cleaned_statutes"
        
        # Access the specific database and collections
        database = db[database_name]
        source_collection = database[source_collection_name]
        target_collection = database[target_collection_name]
        
        logger.info(f"Starting cleaning operation from {source_collection_name} to {target_collection_name}")
        
        # Get enabled mappings
        enabled_mappings = [m for m in request.mappings if m.enabled]
        if not enabled_mappings:
            return {
                "success": False,
                "message": "No enabled field mappings provided",
                "changes_count": 0,
                "sample_changes": []
            }
        
        logger.info(f"Applying {len(enabled_mappings)} field mappings")
        
        # Get documents to clean based on scope
        if request.scope == "all":
            cursor = source_collection.find({})
        else:
            # For now, treat any non-"all" scope as all documents
            # Future enhancement: support specific statute selection
            cursor = source_collection.find({})
        
        documents = list(cursor)
        if not documents:
            return {
                "success": False,
                "message": "No documents found to clean",
                "changes_count": 0,
                "sample_changes": []
            }
        
        logger.info(f"Found {len(documents)} documents to process")
        
        # Process documents and track changes
        changes_count = 0
        sample_changes = []
        processed_documents = []
        
        for doc in documents:
            sections = doc.get("Sections", [])
            if not sections:
                processed_documents.append(doc)
                continue
            
            # Track changes for this document
            doc_changes = []
            modified_sections = []
            
            for section in sections:
                modified_section = section.copy()
                section_changes = []
                
                # Apply each mapping
                for mapping in enabled_mappings:
                    source_field = mapping.source
                    target_field = mapping.target
                    
                    if source_field in section and source_field != target_field:
                        # Move/rename field
                        value = section[source_field]
                        modified_section[target_field] = value
                        
                        # Remove old field if it's different from target
                        if source_field != target_field:
                            if source_field in modified_section:
                                del modified_section[source_field]
                        
                        section_changes.append({
                            "field_mapping": f"{source_field} → {target_field}",
                            "value_preview": str(value)[:100] + "..." if len(str(value)) > 100 else str(value)
                        })
                
                if section_changes:
                    doc_changes.extend(section_changes)
                
                modified_sections.append(modified_section)
            
            if doc_changes:
                changes_count += 1
                
                # Add to sample changes (limit to first 5)
                if len(sample_changes) < 5:
                    sample_changes.append({
                        "statute_name": doc.get("Statute_Name", "Unknown"),
                        "sections_modified": len([s for s in sections if any(mapping.source in s for mapping in enabled_mappings)]),
                        "field_changes": doc_changes[:5]  # Limit for readability
                    })
            
            # Create updated document
            updated_doc = doc.copy()
            updated_doc["Sections"] = modified_sections
            updated_doc["cleaned_at"] = datetime.now(timezone.utc).isoformat()
            updated_doc["field_mappings_applied"] = [
                {"source": m.source, "target": m.target}
                for m in enabled_mappings
            ]
            
            processed_documents.append(updated_doc)
        
        # Clear target collection and insert cleaned documents
        await target_collection.delete_many({})
        
        if processed_documents:
            result = await target_collection.insert_many(processed_documents)
            logger.info(f"Inserted {len(result.inserted_ids)} cleaned documents")
        
        return {
            "success": True,
            "message": f"Field cleaning applied successfully to {len(processed_documents)} documents",
            "changes_count": changes_count,
            "total_documents": len(processed_documents),
            "mappings_applied": len(enabled_mappings),
            "sample_changes": sample_changes,
            "target_collection": target_collection_name,
            "applied_at": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error applying cleaning: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to apply cleaning: {str(e)}"
        )

@router.post("/diagnostic-section-counts")
async def diagnostic_section_counts(config: NormalizationConfig = NormalizationConfig()):
    """
    Diagnostic endpoint to compare section counts between raw and normalized collections.
    This helps identify if sections are being lost during normalization.
    """
    try:
        db = await get_db()
        database_name = config.database_name or DEFAULT_DATABASE_NAME
        database = db[database_name]
        
        # Get collections
        raw_collection = database[config.source_collection]
        normalized_collection = database[config.target_collection]
        
        logger.info(f"Analyzing section counts: {config.source_collection} vs {config.target_collection}")
        
        # Count documents in each collection
        raw_count = await raw_collection.count_documents({})
        normalized_count = await normalized_collection.count_documents({})
        
        # Sample raw documents to understand structure
        raw_sample = await raw_collection.find({}).limit(5).to_list(length=5)
        normalized_sample = await normalized_collection.find({}).limit(3).to_list(length=3)
        
        # Count total sections in raw collection (assuming each raw doc is a section)
        raw_total_sections = raw_count  # If each raw document is a section
        
        # Alternative: if raw documents have sections arrays
        raw_sections_with_arrays_pipeline = [
            {"$project": {"section_count": {"$size": {"$ifNull": ["$Sections", []]}}}},
            {"$group": {"_id": None, "total_sections": {"$sum": "$section_count"}}}
        ]
        raw_sections_with_arrays = await raw_collection.aggregate(raw_sections_with_arrays_pipeline).to_list(length=1)
        raw_sections_from_arrays = raw_sections_with_arrays[0]["total_sections"] if raw_sections_with_arrays else 0
        
        # Count total sections in normalized collection
        normalized_sections_pipeline = [
            {"$project": {"section_count": {"$size": {"$ifNull": ["$Sections", []]}}}},
            {"$group": {"_id": None, "total_sections": {"$sum": "$section_count"}}}
        ]
        normalized_sections_result = await normalized_collection.aggregate(normalized_sections_pipeline).to_list(length=1)
        normalized_total_sections = normalized_sections_result[0]["total_sections"] if normalized_sections_result else 0
        
        # Analyze raw document structure
        raw_structure_analysis = {}
        if raw_sample:
            first_raw = raw_sample[0]
            raw_structure_analysis = {
                "sample_fields": list(first_raw.keys()),
                "has_sections_array": "Sections" in first_raw,
                "sections_array_length": len(first_raw.get("Sections", [])) if "Sections" in first_raw else 0,
                "sample_statute_name": first_raw.get("Statute_Name", first_raw.get("statute_name", "Not found")),
                "sample_section_info": {
                    "section_field": first_raw.get("Section", "Not found"),
                    "number_field": first_raw.get("number", "Not found"),
                    "definition_field": bool(first_raw.get("definition", False))
                }
            }
        
        # Analyze normalized document structure
        normalized_structure_analysis = {}
        if normalized_sample:
            first_normalized = normalized_sample[0]
            normalized_structure_analysis = {
                "sample_fields": list(first_normalized.keys()),
                "sections_array_length": len(first_normalized.get("Sections", [])),
                "sample_statute_name": first_normalized.get("Statute_Name", "Not found"),
                "sections_sample": first_normalized.get("Sections", [])[:3] if first_normalized.get("Sections") else []
            }
        
        return {
            "success": True,
            "message": "Section count diagnostic analysis",
            "raw_collection": {
                "name": config.source_collection,
                "total_documents": raw_count,
                "assuming_each_doc_is_section": raw_total_sections,
                "sections_from_arrays": raw_sections_from_arrays,
                "structure_analysis": raw_structure_analysis
            },
            "normalized_collection": {
                "name": config.target_collection,
                "total_documents": normalized_count,
                "total_sections": normalized_total_sections,
                "avg_sections_per_statute": round(normalized_total_sections / normalized_count, 2) if normalized_count > 0 else 0,
                "structure_analysis": normalized_structure_analysis
            },
            "comparison": {
                "document_reduction": f"{raw_count} → {normalized_count} ({((normalized_count/raw_count)*100):.1f}%)" if raw_count > 0 else "N/A",
                "section_count_comparison": {
                    "raw_as_individual_docs": raw_total_sections,
                    "raw_from_arrays": raw_sections_from_arrays,
                    "normalized_grouped": normalized_total_sections
                },
                "potential_issues": []
            },
            "analysis_timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in diagnostic section counts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze section counts: {str(e)}"
        )

@router.get("/progress-status")
async def get_progress_status():
    """
    Get the current progress status of normalization operations.
    """
    try:
        # For now, return a basic status response
        # This can be enhanced to track actual progress in the future
        return {
            "status": "ready",
            "message": "Normalization system is ready",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting progress status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get progress status: {str(e)}"
        )

@router.get("/normalization-history")
async def get_normalization_history(limit: int = 10):
    """
    Get the history of normalization operations.
    """
    try:
        # For now, return an empty history
        # This can be enhanced to track actual history in the future
        return {
            "history": [],
            "limit": limit,
            "total": 0,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting normalization history: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get normalization history: {str(e)}"
        )