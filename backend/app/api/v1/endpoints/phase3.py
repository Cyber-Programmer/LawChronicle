from fastapi import APIRouter, HTTPException, BackgroundTasks, status
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import subprocess
import tempfile
import os
import sys
from pathlib import Path
import json
from datetime import datetime, date
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import glob
from collections import Counter

router = APIRouter()

# Configuration model - updated to match CLI flow
class Phase3Config(BaseModel):
    source_database: str = "Statutes"
    source_collection: str = "normalized_statutes"
    target_database: str = "Batched-Statutes"
    target_collection_prefix: str = "batch"
    batch_size: int = 10
    enable_ai_cleaning: bool = False

# New models for batch cleaning
class BatchCleaningConfig(BaseModel):
    target_database: str = "Batched-Statutes"
    target_collection_prefix: str = "batch"
    batch_numbers: Optional[List[int]] = None  # None means all batches
    clean_all: bool = True

# Constants - updated to match CLI scripts
MONGODB_URI = "mongodb://localhost:27017"
DEFAULT_SOURCE_DB = "Statutes"
DEFAULT_SOURCE_COLL = "normalized_statutes"
DEFAULT_TARGET_DB = "Batched-Statutes"
DEFAULT_TARGET_COLL_PREFIX = "batch"
DEFAULT_BATCH_SIZE = 10

# Pakistani provinces from CLI script
PAKISTANI_PROVINCES = [
    'Azad Kashmir And Jammu', 'Balochistan', 'Federal', 'Khyber Pakhtunkhwa', 'Punjab', 'Sindh'
]

FOREIGN_COUNTRY_INDICATORS = [
    'india', 'indian', 'turkey', 'turkish', 'uk', 'united kingdom', 'england', 'scotland', 'wales', 'ireland',
    'united states', 'usa', 'america', 'bangladesh', 'sri lanka', 'nepal', 'afghanistan', 'iran', 'china', 'russia',
    'malaysia', 'canada', 'australia', 'france', 'germany', 'japan', 'italy', 'spain', 'sweden', 'norway', 'denmark',
    'netherlands', 'switzerland', 'belgium', 'brazil', 'mexico', 'south africa', 'egypt', 'indonesia', 'thailand'
]

class SectionSplittingEngine:
    """Handles splitting normalized statutes into batches"""
    
    @staticmethod
    def split_statutes_into_batches(statutes: List[Dict[str, Any]], batch_size: int) -> List[List[Dict[str, Any]]]:
        """Split statutes into batches of specified size"""
        batches = []
        total = len(statutes)
        
        for i in range(0, total, batch_size):
            batch = statutes[i:i + batch_size]
            batches.append(batch)
        
        return batches
    
    @staticmethod
    def create_batch_collections(source_db, target_db, batch_size: int, source_collection: str, target_database: str, target_prefix: str):
        """Create batch collections from source collection and generate metadata"""
        import json
        from datetime import date
        import os
        from pymongo import MongoClient
        
        # Use sync client for this operation
        sync_client = MongoClient(MONGODB_URI)
        sync_source_db = sync_client[source_db.name]
        sync_target_db = sync_client[target_database]
        
        source_coll = sync_source_db[source_collection]
        statutes = list(source_coll.find({}))
        batches = SectionSplittingEngine.split_statutes_into_batches(statutes, batch_size)
        batch_collections = []
        metadata = {
            "total_statutes_processed": len(statutes),
            "splits_created": len(batches),
            "splitting_stats": {
                "base_chunk_size": batch_size,
                "chunk_sizes": [len(batch) for batch in batches],
                "total_sections_distributed": sum(len(doc.get("Sections", [])) for doc in statutes),
            },
            "database_distribution": {
                "statutes_per_database": {},
                "sections_per_database": {},
                "database_sizes": {}
            },
            "processing_details": {
                "databases_cleared": 0,
                "total_documents_inserted": 0,
                "insertion_errors": 0
            },
            "script": "api_phase3_split",
            "db_name": target_database,
            "collection": target_prefix,
            "date": date.today().isoformat()
        }
        
        for i, batch in enumerate(batches):
            batch_name = f"{target_prefix}{i+1}"
            batch_coll = sync_target_db[batch_name]
            batch_coll.delete_many({})
            metadata["processing_details"]["databases_cleared"] += 1
            batch_statutes = 0
            batch_sections = 0
            for doc in batch:
                doc_copy = doc.copy()
                doc_copy.pop("_id", None)
                try:
                    batch_coll.insert_one(doc_copy)
                    metadata["processing_details"]["total_documents_inserted"] += 1
                    batch_statutes += 1
                    batch_sections += len(doc_copy.get("Sections", []))
                except Exception:
                    metadata["processing_details"]["insertion_errors"] += 1
            batch_collections.append({
                "name": batch_name,
                "statute_count": batch_statutes,
                "section_count": batch_sections
            })
            metadata["database_distribution"]["statutes_per_database"][batch_name] = batch_statutes
            metadata["database_distribution"]["sections_per_database"][batch_name] = batch_sections
            metadata["database_distribution"]["database_sizes"][batch_name] = {
                "statutes": batch_statutes,
                "sections": batch_sections,
                "average_sections_per_statute": batch_sections / batch_statutes if batch_statutes > 0 else 0
            }
        
        # Save metadata file
        metadata_dir = os.path.join(os.path.dirname(__file__), '../../metadata')
        os.makedirs(metadata_dir, exist_ok=True)
        meta_filename = f"metadata_split_{target_database}_{target_prefix}_{date.today().isoformat()}.json"
        meta_path = os.path.join(metadata_dir, meta_filename)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        metadata["metadata_file"] = meta_path
        
        sync_client.close()
        return batch_collections, metadata

class FieldCleaningEngine:
    """Handles cleaning of statute fields per batch"""
    
    @staticmethod
    def clean_text_field(text: str) -> str:
        """Clean text fields by removing extra whitespace and normalizing"""
        if not text:
            return ""
        
        # Remove extra whitespace and newlines
        cleaned = " ".join(text.split())
        # Remove special characters but keep basic punctuation
        cleaned = "".join(c for c in cleaned if c.isalnum() or c.isspace() or c in ".,;:()[]{}'\"-")
        return cleaned.strip()
    
    @staticmethod
    def validate_pakistan_law(doc: Dict[str, Any]) -> bool:
        """Check if document is a Pakistan law using CLI logic"""
        preamble = doc.get("Preamble", "")
        statute_name = doc.get("Statute_Name", "")
        province = doc.get("Province", "")
        date_str = doc.get("Date", "")
        
        # Check for pre-1947 laws
        if date_str:
            try:
                from dateutil import parser
                dt = parser.parse(date_str, fuzzy=True, dayfirst=True)
                if dt.year < 1947:
                    return False
            except:
                pass
        
        # Check for Pakistan mentions
        if "pakistan" in preamble.lower() or "pakistan" in statute_name.lower():
            return True
        
        # Check for Pakistani provinces
        if province in PAKISTANI_PROVINCES:
            return True
        
        # Check for Gazette of Pakistan mentions
        if "gazette of pakistan" in preamble.lower():
            return True
        
        return False
    
    @staticmethod
    def drop_unnecessary_fields(doc: Dict[str, Any]) -> Dict[str, Any]:
        """Drop fields that are not needed for processing"""
        # Keep essential fields
        essential_fields = {
            "Statute_Name", "Sections", "Province", "Date", "Year", 
            "Statute_Type", "Bookmark_ID", "Blob_Url"
        }
        
        cleaned_doc = {}
        for field, value in doc.items():
            if field in essential_fields or field.startswith("Section_"):
                cleaned_doc[field] = value
        
        return cleaned_doc
    
    @staticmethod
    def bring_common_fields_up(doc: Dict[str, Any]) -> Dict[str, Any]:
        """Bring common fields from sections up to statute level"""
        sections = doc.get("Sections", [])
        if not sections:
            return doc
        
        # Find common fields across all sections
        common_fields = {}
        if sections:
            first_section = sections[0]
            for field, value in first_section.items():
                if all(section.get(field) == value for section in sections):
                    common_fields[field] = value
        
        # Move common fields up and remove from sections
        for field, value in common_fields.items():
            doc[field] = value
            for section in sections:
                section.pop(field, None)
        
        return doc
    
    @staticmethod
    def clean_single_section_statutes(doc: Dict[str, Any]) -> Dict[str, Any]:
        """Handle single-section statutes specially"""
        sections = doc.get("Sections", [])
        if len(sections) == 1:
            # For single sections, promote section content to top level
            section = sections[0]
            for field, value in section.items():
                if field not in doc:
                    doc[field] = value
            # Keep the sections array for consistency
        return doc
    
    @staticmethod
    def remove_preamble_duplicates(doc: Dict[str, Any]) -> Dict[str, Any]:
        """Remove duplicate preamble sections"""
        sections = doc.get("Sections", [])
        if not sections:
            return doc
        
        # Find and remove duplicate preamble sections
        seen_preamble = False
        cleaned_sections = []
        
        for section in sections:
            section_name = section.get("Section", "").strip().upper()
            if section_name == "PREAMBLE":
                if not seen_preamble:
                    cleaned_sections.append(section)
                    seen_preamble = True
            else:
                cleaned_sections.append(section)
        
        doc["Sections"] = cleaned_sections
        return doc
    
    @staticmethod
    def sort_sections_within_statutes(doc: Dict[str, Any]) -> Dict[str, Any]:
        """Sort sections within statutes: preamble first, then numeric, then text"""
        sections = doc.get("Sections", [])
        if not sections:
            return doc
        
        def section_sort_key(section):
            section_name = section.get("Section", "").strip()
            
            # Preamble first
            if section_name.upper() == "PREAMBLE":
                return (0, 0, section_name)
            
            # Try to extract numeric part
            try:
                numeric_part = int(''.join(filter(str.isdigit, section_name)))
                return (1, numeric_part, section_name)
            except:
                # Text sections last
                return (2, 0, section_name)
        
        sorted_sections = sorted(sections, key=section_sort_key)
        doc["Sections"] = sorted_sections
        return doc
    
    @staticmethod
    def clean_document_structure(doc: Dict[str, Any]) -> Dict[str, Any]:
        """Apply all cleaning steps to a document"""
        # Validate it's a Pakistan law
        if not FieldCleaningEngine.validate_pakistan_law(doc):
            return None  # Document should be dropped
        
        # Apply cleaning steps
        doc = FieldCleaningEngine.drop_unnecessary_fields(doc)
        doc = FieldCleaningEngine.bring_common_fields_up(doc)
        doc = FieldCleaningEngine.clean_single_section_statutes(doc)
        doc = FieldCleaningEngine.remove_preamble_duplicates(doc)
        doc = FieldCleaningEngine.sort_sections_within_statutes(doc)
        
        # Add cleaning metadata
        doc["cleaned_at"] = datetime.now().isoformat()
        doc["cleaning_version"] = "1.0"
        
        return doc

class ScriptGenerator:
    """Generates Python scripts for processing"""
    
    @staticmethod
    def generate_section_splitting_script(config: Phase3Config) -> str:
        """Generate script for section splitting"""
        script = f'''
# -*- coding: utf-8 -*-
import math
from pymongo import MongoClient
from tqdm import tqdm
import json
from datetime import datetime, date
import os
import numpy as np
from collections import defaultdict, Counter

# Configuration
SRC_DB = "{config.source_database}"
SRC_COLL = "{config.source_collection}"
TARGET_DB = "{config.target_database}"
TARGET_COLL_PREFIX = "{config.target_collection_prefix}"
NUM_SPLITS = {config.batch_size}

def analyze_statute_content(statute):
    """Analyze statute content for metadata"""
    sections = statute.get("Sections", [])
    section_count = len(sections)
    
    has_preamble = False
    if sections:
        section_names = [section.get("Section", "").strip().upper() for section in sections]
        has_preamble = "PREAMBLE" in section_names
    
    return {{
        "section_count": section_count,
        "has_preamble": has_preamble,
        "has_multiple_sections": section_count > 1
    }}

def main():
    print("Connecting to MongoDB...")
    client = MongoClient("mongodb://localhost:27017/")
    src_coll = client[SRC_DB][SRC_COLL]

    print("Fetching all statutes from source collection...")
    statutes = list(src_coll.find({{}}))
    total = len(statutes)
    print(f"Fetched {{total}} statutes.")

    # Calculate chunk sizes
    base_size = total // NUM_SPLITS
    last_size = total - base_size * (NUM_SPLITS - 1)
    sizes = [base_size] * (NUM_SPLITS - 1) + [last_size]

    print(f"Splitting into {{NUM_SPLITS}} databases: {{sizes}} entities each.")

    start = 0
    for i, size in enumerate(tqdm(sizes, desc="Splitting statutes")):
        db_name = TARGET_DB
        batch_name = f"{{TARGET_COLL_PREFIX}}{{i+1}}"
        split_coll = client[db_name][batch_name]
        
        print(f"Writing {{size}} statutes to {{db_name}}.{{batch_name}} ...")
        
        # Clear target collection first
        split_coll.delete_many({{}})
        
        chunk = statutes[start:start+size]
        
        for doc in tqdm(chunk, desc=f"Inserting into {{batch_name}}"):
            # Insert document
            try:
                doc_copy = doc.copy()
                doc_copy.pop("_id", None)
                split_coll.insert_one(doc_copy)
            except Exception as e:
                print(f"Error inserting document: {{e}}")
        
        start += size

    print(f"\\n[SUCCESS] All splits completed successfully.")

if __name__ == "__main__":
    main()
'''
        return script
    
    @staticmethod
    def generate_field_cleaning_script(config: Phase3Config) -> str:
        """Generate script for field cleaning per batch"""
        script = f'''
# -*- coding: utf-8 -*-
import re
from datetime import datetime
from pymongo import MongoClient
from tqdm import tqdm
import json
from collections import defaultdict, Counter

# Configuration
MONGO_URI = "mongodb://localhost:27017"
TARGET_DB = "{config.target_database}"
TARGET_COLL_PREFIX = "{config.target_collection_prefix}"
NUM_BATCHES = {config.batch_size}

# Fields to drop at statute level
FIELDS_TO_DROP = [
    "Source", "Category", "PDF_URL", "Blob_Url", "Statute_RAG_Content", "Statute_HTML"
]

# Fields to drop at section level
SECTION_FIELDS_TO_DROP = [
    "Statute_RAG_Content", "Statute_HTML", "PDF_URL", "Blob_Url"
]

def find_common_fields(sections):
    """Find fields that are present in every section and have the same value in all sections"""
    if not sections:
        return {{}}
    
    # Get fields present in ALL sections
    common_field_candidates = set(sections[0].keys()) if sections else set()
    for section in sections[1:]:
        common_field_candidates &= set(section.keys())
    
    # Remove standard section identifiers that shouldn't be moved up
    common_field_candidates.discard("Section")
    common_field_candidates.discard("Content")
    common_field_candidates.discard("_id")
    
    # Check if common fields have the same value across all sections
    common_fields = {{}}
    for field in common_field_candidates:
        first_value = sections[0][field]
        if all(section.get(field) == first_value for section in sections):
            common_fields[field] = first_value
    
    return common_fields

def clean_document_fields(doc):
    """Apply field-level cleaning operations to a document"""
    changes_made = False
    cleaning_log = {{
        "fields_dropped": [],
        "section_fields_dropped": [],
        "common_fields_moved_up": [],
        "text_fields_cleaned": []
    }}
    
    # 1. Drop unnecessary top-level fields
    for field in FIELDS_TO_DROP:
        if field in doc:
            del doc[field]
            changes_made = True
            cleaning_log["fields_dropped"].append(field)
    
    # 2. Clean text fields - normalize whitespace
    for field in ["Statute_Name", "Preamble"]:
        if field in doc and doc[field]:
            original = str(doc[field])
            cleaned = " ".join(original.split())
            if cleaned != original:
                doc[field] = cleaned
                changes_made = True
                cleaning_log["text_fields_cleaned"].append(field)
    
    # 3. Process sections if they exist
    if "Sections" in doc and isinstance(doc["Sections"], list):
        sections = doc["Sections"]
        
        # Find and move common fields up to statute level
        common_fields = find_common_fields(sections)
        for field, value in common_fields.items():
            if field not in doc:  # Don't overwrite existing statute-level fields
                doc[field] = value
                changes_made = True
                cleaning_log["common_fields_moved_up"].append(field)
        
        # Remove common fields from sections and drop unnecessary section fields
        for section in sections:
            # Remove common fields that were moved up
            for field in common_fields:
                if field in section:
                    del section[field]
                    changes_made = True
            
            # Remove unnecessary section fields
            for field in SECTION_FIELDS_TO_DROP:
                if field in section:
                    del section[field]
                    changes_made = True
                    if field not in cleaning_log["section_fields_dropped"]:
                        cleaning_log["section_fields_dropped"].append(field)
            
            # Clean section text content
            if "Content" in section and section["Content"]:
                original = str(section["Content"])
                cleaned = " ".join(original.split())
                if cleaned != original:
                    section["Content"] = cleaned
                    changes_made = True
    
    # Add cleaning metadata
    if changes_made:
        doc["field_cleaned_at"] = datetime.now().isoformat()
        doc["field_cleaning_version"] = "1.0"
        doc["field_cleaning_log"] = cleaning_log
    
    return doc, changes_made

def main():
    print("Connecting to MongoDB...")
    client = MongoClient(MONGO_URI)
    
    total_processed = 0
    total_cleaned = 0
    total_unchanged = 0
    
    cleaning_stats = {{
        "fields_dropped_count": Counter(),
        "section_fields_dropped_count": Counter(),
        "common_fields_moved_count": Counter(),
        "text_fields_cleaned_count": Counter()
    }}
    
    for batch_num in range(1, NUM_BATCHES + 1):
        batch_name = f"{{TARGET_COLL_PREFIX}}{{batch_num}}"
        batch_coll = client[TARGET_DB][batch_name]
        
        print(f"\\nProcessing batch {{batch_name}}...")
        
        # Get all documents in this batch
        documents = list(batch_coll.find({{}}))
        batch_cleaned = 0
        batch_unchanged = 0
        
        for doc in tqdm(documents, desc=f"Cleaning {{batch_name}}"):
            total_processed += 1
            
            # Clean the document fields
            cleaned_doc, changes_made = clean_document_fields(doc)
            
            if changes_made:
                # Update the document in place
                batch_coll.replace_one({{"_id": doc["_id"]}}, cleaned_doc)
                batch_cleaned += 1
                total_cleaned += 1
                
                # Update statistics
                if "field_cleaning_log" in cleaned_doc:
                    log = cleaned_doc["field_cleaning_log"]
                    for field in log.get("fields_dropped", []):
                        cleaning_stats["fields_dropped_count"][field] += 1
                    for field in log.get("section_fields_dropped", []):
                        cleaning_stats["section_fields_dropped_count"][field] += 1
                    for field in log.get("common_fields_moved_up", []):
                        cleaning_stats["common_fields_moved_count"][field] += 1
                    for field in log.get("text_fields_cleaned", []):
                        cleaning_stats["text_fields_cleaned_count"][field] += 1
            else:
                batch_unchanged += 1
                total_unchanged += 1
        
        print(f"Batch {{batch_name}}: {{len(documents)}} processed, {{batch_cleaned}} cleaned, {{batch_unchanged}} unchanged")
    
    print(f"\\n[SUCCESS] Field cleaning completed!")
    print(f"Total processed: {{total_processed}}")
    print(f"Total cleaned: {{total_cleaned}}")
    print(f"Total unchanged: {{total_unchanged}}")
    
    print(f"\\nCleaning Statistics:")
    print(f"Top-level fields dropped: {{dict(cleaning_stats['fields_dropped_count'])}}")
    print(f"Section fields dropped: {{dict(cleaning_stats['section_fields_dropped_count'])}}")
    print(f"Common fields moved up: {{dict(cleaning_stats['common_fields_moved_count'])}}")
    print(f"Text fields cleaned: {{dict(cleaning_stats['text_fields_cleaned_count'])}}")

if __name__ == "__main__":
    main()
'''
        return script

# Metadata and History utilities
class MetadataManager:
    """Manages metadata files and history"""
    
    @staticmethod
    def get_metadata_directory():
        """Get metadata directory path"""
        return os.path.join(os.path.dirname(__file__), '../../metadata')
    
    @staticmethod
    def list_metadata_files():
        """List all metadata files with basic info"""
        metadata_dir = MetadataManager.get_metadata_directory()
        if not os.path.exists(metadata_dir):
            return []
        
        files = glob.glob(os.path.join(metadata_dir, "metadata_*.json"))
        metadata_list = []
        
        for file_path in sorted(files, reverse=True):  # Most recent first
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Extract info from filename and data
                filename = os.path.basename(file_path)
                operation_type = "split" if "split" in filename else "clean" if "clean" in filename else "unknown"
                
                metadata_list.append({
                    "filename": filename,
                    "filepath": file_path,
                    "operation_type": operation_type,
                    "database": data.get("db_name", "unknown"),
                    "collection": data.get("collection", "unknown"),
                    "date": data.get("date", "unknown"),
                    "total_processed": data.get("total_statutes_processed", 0),
                    "created_at": datetime.fromtimestamp(os.path.getctime(file_path)).isoformat()
                })
            except Exception as e:
                print(f"Error reading metadata file {file_path}: {e}")
                continue
        
        return metadata_list
    
    @staticmethod
    def get_metadata_content(filename: str):
        """Get full content of a metadata file"""
        metadata_dir = MetadataManager.get_metadata_directory()
        file_path = os.path.join(metadata_dir, filename)
        
        if not os.path.exists(file_path):
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading metadata file {file_path}: {e}")
            return None
    
    @staticmethod
    def save_cleaning_metadata(config: BatchCleaningConfig, stats: Dict, batches_processed: List[str]):
        """Save metadata for cleaning operations"""
        metadata = {
            "operation_type": "field_cleaning",
            "total_batches_processed": len(batches_processed),
            "batches_processed": batches_processed,
            "cleaning_stats": stats,
            "configuration": {
                "target_database": config.target_database,
                "target_collection_prefix": config.target_collection_prefix,
                "batch_numbers": config.batch_numbers,
                "clean_all": config.clean_all
            },
            "script": "api_phase3_clean",
            "db_name": config.target_database,
            "collection": config.target_collection_prefix,
            "date": date.today().isoformat(),
            "timestamp": datetime.now().isoformat()
        }
        
        metadata_dir = MetadataManager.get_metadata_directory()
        os.makedirs(metadata_dir, exist_ok=True)
        
        # Generate filename with batch info
        batch_suffix = "all" if config.clean_all else f"batches_{'_'.join(map(str, config.batch_numbers))}"
        meta_filename = f"metadata_clean_{config.target_database}_{config.target_collection_prefix}_{batch_suffix}_{date.today().isoformat()}.json"
        meta_path = os.path.join(metadata_dir, meta_filename)
        
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        return meta_path

class ScriptExecutor:
    """Executes generated Python scripts"""
    
    @staticmethod
    def execute_script(script_content: str, config: Phase3Config) -> Dict[str, Any]:
        """Execute a Python script"""
        try:
            # Create temporary script file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(script_content)
                script_path = f.name
            
            # Get backend directory for proper execution context
            backend_dir = Path(__file__).parent.parent.parent.parent
            
            # Execute script with proper encoding
            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=600,  # 10 minute timeout
                cwd=str(backend_dir),
                env={
                    **os.environ,
                    'PYTHONPATH': str(backend_dir),
                    'PYTHONIOENCODING': 'utf-8'
                }
            )
            
            # Clean up
            os.unlink(script_path)
            
            # Handle encoding issues in output
            try:
                stdout = result.stdout if result.stdout else ''
                stderr = result.stderr if result.stderr else ''
            except UnicodeDecodeError:
                stdout = result.stdout.encode('utf-8', errors='replace').decode('utf-8') if result.stdout else ''
                stderr = result.stderr.encode('utf-8', errors='replace').decode('utf-8') if result.stderr else ''
            
            return {
                'success': result.returncode == 0,
                'stdout': stdout,
                'stderr': stderr,
                'return_code': result.returncode
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'stdout': '',
                'stderr': str(e)
            }

# API Endpoints
@router.get("/status")
async def get_phase3_status():
    """Get current status of Phase 3"""
    try:
        # Connect to MongoDB
        client = AsyncIOMotorClient(MONGODB_URI)
        
        # Check source collection
        source_db = client[DEFAULT_SOURCE_DB]
        source_exists = DEFAULT_SOURCE_COLL in await source_db.list_collection_names()
        source_count = await source_db[DEFAULT_SOURCE_COLL].count_documents({}) if source_exists else 0
        
        # Check target database and batch collections
        target_db = client[DEFAULT_TARGET_DB]
        target_exists = DEFAULT_TARGET_DB in await client.list_database_names()
        
        batch_collections = []
        if target_exists:
            batch_collections = [name for name in await target_db.list_collection_names() 
                               if name.startswith(DEFAULT_TARGET_COLL_PREFIX)]
        
        return {
            "status": "success",
            "collection_status": {
                "source_exists": source_exists,
                "source_count": source_count,
                "target_database_exists": target_exists,
                "batch_collections": batch_collections,
                "batch_count": len(batch_collections)
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error checking status: {str(e)}"
        )

@router.post("/start-section-splitting")
async def start_section_splitting(config: Phase3Config):
    """Start section splitting process with metadata generation"""
    try:
        client = AsyncIOMotorClient(MONGODB_URI)
        source_db = client[config.source_database]
        target_db = client[config.target_database]
        
        # Check if source collection exists
        if config.source_collection not in await source_db.list_collection_names():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source collection '{config.source_collection}' not found in database '{config.source_database}'"
            )
        
        # Perform splitting and get metadata
        batch_collections, metadata = SectionSplittingEngine.create_batch_collections(
            source_db, target_db, config.batch_size, config.source_collection, 
            config.target_database, config.target_collection_prefix
        )
        
        return {
            "status": "success",
            "message": "Section splitting completed successfully",
            "batches_created": len(batch_collections),
            "total_statutes": metadata.get("total_statutes_processed", 0),
            "metadata_file": os.path.basename(metadata.get("metadata_file", "")),
            "batch_collections": batch_collections,
            "config": config.dict()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error starting section splitting: {str(e)}"
        )

@router.post("/start-field-cleaning")
async def start_field_cleaning(config: Phase3Config, background_tasks: BackgroundTasks):
    """Start field cleaning process on batches"""
    try:
        # Generate cleaning script
        script = ScriptGenerator.generate_field_cleaning_script(config)
        
        # Execute in background
        background_tasks.add_task(execute_field_cleaning, script, config)
        
        return {
            "status": "success",
            "message": "Field cleaning started in background",
            "config": config.dict()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error starting field cleaning: {str(e)}"
        )

@router.post("/preview-batches")
async def preview_batches(config: Phase3Config):
    """Preview batch collections"""
    try:
        client = AsyncIOMotorClient(MONGODB_URI)
        target_db = client[config.target_database]
        
        if config.target_database not in await client.list_database_names():
            return {
                "status": "success",
                "message": "Target database does not exist",
                "batches": []
            }
        
        batch_collections = [name for name in await target_db.list_collection_names() 
                           if name.startswith(config.target_collection_prefix)]
        
        preview_data = []
        # Helper to convert ObjectId to string for JSON serialization
        def convert_objectid(obj):
            if isinstance(obj, dict):
                return {k: convert_objectid(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_objectid(item) for item in obj]
            try:
                from bson import ObjectId
                if isinstance(obj, ObjectId):
                    return str(obj)
            except ImportError:
                pass
            return obj
        for batch_name in batch_collections[:3]:  # Preview first 3 batches
            batch_coll = target_db[batch_name]
            sample_docs = await batch_coll.find().limit(2).to_list(2)
            sample_docs_serialized = [convert_objectid(doc) for doc in sample_docs]
            preview_data.append({
                "batch_name": batch_name,
                "document_count": await batch_coll.count_documents({}),
                "sample_documents": sample_docs_serialized
            })
        
        return {
            "status": "success",
            "batches": preview_data
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error previewing batches: {str(e)}"
        )

@router.post("/statistics")
async def get_phase3_statistics(config: Phase3Config):
    """Get Phase 3 processing statistics"""
    try:
        client = AsyncIOMotorClient(MONGODB_URI)
        
        # Source collection stats
        source_db = client[config.source_database]
        source_count = 0
        if config.source_collection in await source_db.list_collection_names():
            source_count = await source_db[config.source_collection].count_documents({})
        
        # Target database stats
        target_exists = config.target_database in await client.list_database_names()
        batch_collections = []
        total_batch_docs = 0
        
        if target_exists:
            target_db = client[config.target_database]
            batch_collections = [name for name in await target_db.list_collection_names() 
                               if name.startswith(config.target_collection_prefix)]
            
            for batch_name in batch_collections:
                batch_coll = target_db[batch_name]
                batch_count = await batch_coll.count_documents({})
                total_batch_docs += batch_count
        
        return {
            "status": "success",
            "statistics": {
                "source_collection": {
                    "name": f"{config.source_database}.{config.source_collection}",
                    "count": source_count,
                    "exists": source_count > 0
                },
                "target_database": {
                    "name": config.target_database,
                    "exists": target_exists,
                    "batch_collections": batch_collections,
                    "total_batch_documents": total_batch_docs
                }
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting statistics: {str(e)}"
        )

@router.post("/rollback")
async def rollback_phase3(config: Phase3Config):
    """Rollback Phase 3 by deleting all created collections"""
    try:
        client = AsyncIOMotorClient(MONGODB_URI)
        
        # Delete target database if it exists
        if config.target_database in await client.list_database_names():
            client.drop_database(config.target_database)
        
        return {
            "status": "success",
            "message": f"Phase 3 rollback completed. Deleted database: {config.target_database}"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error rolling back Phase 3: {str(e)}"
        )

# Background task functions
async def execute_section_splitting(script: str, config: Phase3Config):
    """Execute section splitting script"""
    result = ScriptExecutor.execute_script(script, config)
    print(f"Section splitting result: {result}")

async def execute_field_cleaning(script: str, config: Phase3Config):
    """Execute field cleaning script"""
    result = ScriptExecutor.execute_script(script, config)
    print(f"Field cleaning result: {result}")

# New endpoints for metadata and improved cleaning

@router.post("/generate-metadata")
async def generate_metadata(config: Phase3Config):
    """Generate metadata for existing batch collections"""
    try:
        client = AsyncIOMotorClient(MONGODB_URI)
        target_db = client[config.target_database]
        
        if config.target_database not in await client.list_database_names():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Target database '{config.target_database}' does not exist"
            )
        
        # Get batch collections
        batch_collections = [name for name in await target_db.list_collection_names() 
                           if name.startswith(config.target_collection_prefix)]
        
        if not batch_collections:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No batch collections found with prefix '{config.target_collection_prefix}'"
            )
        
        # Generate metadata for existing batches
        metadata = {
            "total_statutes_processed": 0,
            "splits_created": len(batch_collections),
            "database_distribution": {
                "statutes_per_database": {},
                "sections_per_database": {},
                "database_sizes": {}
            },
            "script": "api_phase3_metadata_generation",
            "db_name": config.target_database,
            "collection": config.target_collection_prefix,
            "date": date.today().isoformat(),
            "timestamp": datetime.now().isoformat()
        }
        
        total_statutes = 0
        for batch_name in batch_collections:
            batch_coll = target_db[batch_name]
            batch_count = await batch_coll.count_documents({})
            
            # Count sections
            sample_docs = await batch_coll.find().limit(100).to_list(100)
            section_count = sum(len(doc.get("Sections", [])) for doc in sample_docs)
            
            total_statutes += batch_count
            metadata["database_distribution"]["statutes_per_database"][batch_name] = batch_count
            metadata["database_distribution"]["sections_per_database"][batch_name] = section_count
            metadata["database_distribution"]["database_sizes"][batch_name] = {
                "statutes": batch_count,
                "sections": section_count,
                "average_sections_per_statute": section_count / batch_count if batch_count > 0 else 0
            }
        
        metadata["total_statutes_processed"] = total_statutes
        
        # Save metadata file
        metadata_dir = MetadataManager.get_metadata_directory()
        os.makedirs(metadata_dir, exist_ok=True)
        meta_filename = f"metadata_generated_{config.target_database}_{config.target_collection_prefix}_{date.today().isoformat()}.json"
        meta_path = os.path.join(metadata_dir, meta_filename)
        
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        return {
            "status": "success",
            "message": "Metadata generated successfully",
            "metadata_file": meta_filename,
            "total_batches": len(batch_collections),
            "total_statutes": total_statutes,
            "metadata": metadata
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating metadata: {str(e)}"
        )

@router.get("/history")
async def get_phase3_history():
    """Get Phase 3 operation history from metadata files"""
    try:
        metadata_files = MetadataManager.list_metadata_files()
        
        return {
            "status": "success",
            "message": f"Found {len(metadata_files)} metadata files",
            "history": metadata_files
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving history: {str(e)}"
        )

@router.get("/history/{filename}")
async def get_metadata_details(filename: str):
    """Get detailed content of a specific metadata file"""
    try:
        content = MetadataManager.get_metadata_content(filename)
        
        if content is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Metadata file '{filename}' not found"
            )
        
        return {
            "status": "success",
            "filename": filename,
            "metadata": content
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving metadata details: {str(e)}"
        )

@router.post("/clean-batches")
async def clean_selected_batches(config: BatchCleaningConfig, background_tasks: BackgroundTasks):
    """Clean selected batches or all batches with metadata generation"""
    try:
        client = AsyncIOMotorClient(MONGODB_URI)
        target_db = client[config.target_database]
        
        if config.target_database not in await client.list_database_names():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Target database '{config.target_database}' does not exist"
            )
        
        # Get available batch collections
        all_batch_collections = [name for name in await target_db.list_collection_names() 
                               if name.startswith(config.target_collection_prefix)]
        
        if not all_batch_collections:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No batch collections found with prefix '{config.target_collection_prefix}'"
            )
        
        # Determine which batches to clean
        if config.clean_all or not config.batch_numbers:
            batches_to_clean = all_batch_collections
        else:
            batches_to_clean = [f"{config.target_collection_prefix}{num}" for num in config.batch_numbers
                              if f"{config.target_collection_prefix}{num}" in all_batch_collections]
        
        if not batches_to_clean:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid batches found to clean"
            )
        
        # Add background task for cleaning
        background_tasks.add_task(execute_batch_cleaning, config, batches_to_clean)
        
        return {
            "status": "success",
            "message": f"Batch cleaning started for {len(batches_to_clean)} batches",
            "batches_to_clean": batches_to_clean,
            "config": config.dict()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error starting batch cleaning: {str(e)}"
        )

@router.post("/available-batches")
async def get_available_batches(config: Phase3Config):
    """Get list of available batch collections for cleaning"""
    try:
        client = AsyncIOMotorClient(MONGODB_URI)
        target_db = client[config.target_database]
        
        if config.target_database not in await client.list_database_names():
            return {
                "status": "success",
                "message": "Target database does not exist",
                "batches": []
            }
        
        batch_collections = [name for name in await target_db.list_collection_names() 
                           if name.startswith(config.target_collection_prefix)]
        
        batch_info = []
        for batch_name in batch_collections:
            batch_coll = target_db[batch_name]
            count = await batch_coll.count_documents({})
            
            # Check if already cleaned
            cleaned_count = await batch_coll.count_documents({"field_cleaned_at": {"$exists": True}})
            
            batch_num = batch_name.replace(config.target_collection_prefix, "")
            batch_info.append({
                "batch_name": batch_name,
                "batch_number": int(batch_num) if batch_num.isdigit() else 0,
                "document_count": count,
                "cleaned_count": cleaned_count,
                "is_cleaned": cleaned_count > 0,
                "cleaning_percentage": (cleaned_count / count * 100) if count > 0 else 0
            })
        
        # Sort by batch number
        batch_info.sort(key=lambda x: x["batch_number"])
        
        return {
            "status": "success",
            "message": f"Found {len(batch_info)} batch collections",
            "batches": batch_info
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving available batches: {str(e)}"
        )

# Background task for batch cleaning
async def execute_batch_cleaning(config: BatchCleaningConfig, batches_to_clean: List[str]):
    """Execute cleaning for selected batches and generate metadata"""
    try:
        client = AsyncIOMotorClient(MONGODB_URI)
        target_db = client[config.target_database]
        
        cleaning_stats = {
            "total_processed": 0,
            "total_cleaned": 0,
            "total_unchanged": 0,
            "fields_dropped_count": Counter(),
            "section_fields_dropped_count": Counter(),
            "common_fields_moved_count": Counter(),
            "text_fields_cleaned_count": Counter(),
            "batch_details": {}
        }
        
        for batch_name in batches_to_clean:
            batch_coll = target_db[batch_name]
            
            print(f"Processing batch {batch_name}...")
            
            # Get all documents in this batch
            documents = await batch_coll.find().to_list(None)
            batch_cleaned = 0
            batch_unchanged = 0
            
            for doc in documents:
                cleaning_stats["total_processed"] += 1
                
                # Apply field cleaning using the FieldCleaningEngine
                cleaned_doc = FieldCleaningEngine.clean_document_structure(doc)
                
                if cleaned_doc is None:
                    # Document was dropped (not a Pakistan law)
                    await batch_coll.delete_one({"_id": doc["_id"]})
                    continue
                
                # Check if changes were made
                if cleaned_doc != doc:
                    # Update the document
                    await batch_coll.replace_one({"_id": doc["_id"]}, cleaned_doc)
                    batch_cleaned += 1
                    cleaning_stats["total_cleaned"] += 1
                    
                    # Update statistics (simplified for now)
                    cleaning_stats["fields_dropped_count"]["various"] += 1
                else:
                    batch_unchanged += 1
                    cleaning_stats["total_unchanged"] += 1
            
            cleaning_stats["batch_details"][batch_name] = {
                "processed": len(documents),
                "cleaned": batch_cleaned,
                "unchanged": batch_unchanged
            }
            
            print(f"Batch {batch_name}: {len(documents)} processed, {batch_cleaned} cleaned, {batch_unchanged} unchanged")
        
        # Save metadata
        metadata_path = MetadataManager.save_cleaning_metadata(config, cleaning_stats, batches_to_clean)
        print(f"Batch cleaning completed. Metadata saved to: {metadata_path}")
        
    except Exception as e:
        print(f"Error in batch cleaning: {str(e)}")
