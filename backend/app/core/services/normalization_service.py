"""
Phase 2 Normalization Service

Extracts complex business logic from phase2 endpoint into testable service modules.
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import subprocess
import tempfile
import os
import re
import logging
from pathlib import Path
import json
from ..config import settings

logger = logging.getLogger(__name__)


class NormalizationEngine:
    """Core normalization business logic"""
    
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp(prefix="lawchronicle_norm_")
    
    def validate_normalization_request(self, source_db: str, target_db: str, 
                                      options: Optional[Dict] = None) -> Dict[str, Any]:
        """Validate normalization parameters"""
        if not source_db or not target_db:
            raise ValueError("Source and target databases are required")
        
        # Check for legacy compatibility mode (same database, different collections)
        if options and options.get("legacy_compatibility") and options.get("same_database_mode"):
            # In legacy mode, we allow "same" database but different collections
            logger.info("🔄 Legacy compatibility mode: Using same database with different collections")
            return {
                "source_db": source_db,
                "target_db": target_db,
                "legacy_mode": True,
                "actual_database": options.get("actual_database"),
                "validated_at": datetime.now().isoformat()
            }
        
        if source_db == target_db:
            raise ValueError("Source and target databases must be different")
            
        return {
            "source_db": source_db,
            "target_db": target_db,
            "validated_at": datetime.now().isoformat()
        }
    
    def generate_normalization_config(self, source_db: str, target_db: str, 
                                    options: Optional[Dict] = None) -> Dict[str, Any]:
        """Generate configuration for normalization process"""
        config = {
            "source": {
                "database": source_db,
                "collection": "raw_statutes"
            },
            "target": {
                "database": target_db,
                "collection": "normalized_statutes"
            },
            "operations": [
                "clean_text_fields",
                "standardize_dates", 
                "extract_metadata",
                "validate_structure"
            ],
            "batch_size": options.get("batch_size", 1000) if options else 1000,
            "created_at": datetime.now().isoformat()
        }
        
        if options:
            config.update(options)
            
        return config
    
    def cleanup(self):
        """Clean up temporary resources"""
        try:
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception as e:
            logger.warning(f"Failed to cleanup temp dir {self.temp_dir}: {e}")


class ScriptRunner:
    """Handles subprocess execution with proper isolation and logging"""
    
    def __init__(self, working_dir: Optional[str] = None):
        self.working_dir = Path(working_dir) if working_dir else Path.cwd()
        
    def validate_script_path(self, script_path: str) -> Path:
        """Validate and normalize script path"""
        path = Path(script_path)
        
        if not path.is_absolute():
            path = self.working_dir / path
            
        if not path.exists():
            raise FileNotFoundError(f"Script not found: {path}")
            
        if not path.suffix == '.py':
            raise ValueError(f"Only Python scripts allowed: {path}")
            
        return path
    
    def run_python_script(self, script_path: str, args: List[str] = None, 
                         timeout: int = 300) -> Dict[str, Any]:
        """Execute Python script with proper error handling"""
        validated_path = self.validate_script_path(script_path)
        args = args or []
        
        cmd = ["python", str(validated_path)] + args
        
        logger.info(f"Executing: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                cwd=self.working_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False  # Don't raise on non-zero exit
            )
            
            return {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "success": result.returncode == 0,
                "executed_at": datetime.now().isoformat()
            }
            
        except subprocess.TimeoutExpired:
            logger.error(f"Script timeout after {timeout}s: {validated_path}")
            raise
        except Exception as e:
            logger.error(f"Script execution failed: {e}")
            raise


class NormalizationService:
    """High-level service orchestrating normalization workflow"""
    
    def __init__(self):
        self.engine = NormalizationEngine()
        self.runner = ScriptRunner()
        
    def start_normalization(self, source_db: str, target_db: str, 
                          options: Optional[Dict] = None) -> Dict[str, Any]:
        """Start the normalization process with actual document processing"""
        from pymongo import MongoClient
        from collections import defaultdict
        import re
        
        try:
            # Validate inputs (pass options for legacy compatibility)
            validation = self.engine.validate_normalization_request(source_db, target_db, options)

            # Get collection names from options (handle None case)
            if options:
                source_collection = options.get("source_collection", "raw_statutes")
                target_collection = options.get("target_collection", "normalized_statutes")
            else:
                source_collection = "raw_statutes"
                target_collection = "normalized_statutes"

            # Use actual database name from validation for legacy mode
            actual_db = validation.get("actual_database", source_db)

            logger.info(f"Starting normalization: {actual_db}.{source_collection} → {actual_db}.{target_collection}")

            # Connect to MongoDB
            client = MongoClient('mongodb://localhost:27017')
            source_col = client[actual_db][source_collection]
            target_col = client[actual_db][target_collection]

            # Clear existing normalized data
            target_col.drop()
            logger.info(f"Cleared existing collection: {target_collection}")

            # Initialize metadata
            metadata = {
                "total_documents_processed": 0,
                "unique_statutes": 0,
                "total_sections": 0,
                "processed_at": datetime.now().isoformat()
            }

            # Group sections by normalized Statute_Name
            statute_dict = defaultdict(list)

            # Process all documents
            cursor = source_col.find({})
            for doc in cursor:
                metadata["total_documents_processed"] += 1

                original_name = doc.get("Statute_Name", "UNKNOWN")
                normalized_name = self._normalize_statute_name(original_name)

                # Remove fields we don't want in the section
                section = {k: v for k, v in doc.items() if k not in ["Statute_Name", "_id"]}
                statute_dict[normalized_name].append(section)

            logger.info(f"Processed {metadata['total_documents_processed']} documents")
            logger.info(f"Found {len(statute_dict)} unique statutes")

            # Build normalized documents
            normalized_docs = []
            for statute_name, sections in statute_dict.items():
                metadata["unique_statutes"] += 1
                metadata["total_sections"] += len(sections)

                # Sort sections (preamble first, then numeric, then alphabetical)
                sections = sorted(sections, key=self._section_sort_key)

                normalized_docs.append({
                    "Statute_Name": statute_name,
                    "Sections": sections
                })

            # Sort statutes alphabetically by name
            normalized_docs.sort(key=lambda x: x["Statute_Name"].lower())

            # Insert into MongoDB
            if normalized_docs:
                target_col.insert_many(normalized_docs)
                target_col.create_index("Statute_Name")
                logger.info(f"Inserted {len(normalized_docs)} normalized statutes")

            # Save metadata to file if requested
            metadata_file_path = None
            if options and options.get("save_metadata"):
                
                # Use unified naming convention: {operation}-{database}-{collection}-{date}.{ext}
                date_str = datetime.now().strftime("%Y-%m-%d")
                operation = "normalize"
                database = actual_db.lower().replace("_", "-")
                collection = source_collection.lower().replace("_", "-")
                filename = f"{operation}-{database}-{collection}-{date_str}.json"
                metadata_dir = os.path.join(os.path.dirname(__file__), "..", "..", "api", "metadata")
                metadata_dir = os.path.abspath(metadata_dir)
                os.makedirs(metadata_dir, exist_ok=True)
                file_path = os.path.join(metadata_dir, filename)
                try:
                    with open(file_path, "w", encoding="utf-8") as f:
                        json.dump(metadata, f, indent=2, ensure_ascii=False)
                    metadata_file_path = file_path
                    logger.info(f"Metadata saved to file: {file_path}")
                except Exception as meta_exc:
                    logger.error(f"Failed to save metadata file: {meta_exc}")

            # Close connection
            client.close()

            # Add metadata file path to response if saved
            if metadata_file_path:
                metadata["metadata_file_path"] = metadata_file_path

            return {
                "status": "completed", 
                "validation": validation,
                "metadata": metadata,
                "message": f"Successfully normalized {metadata['total_documents_processed']} documents into {metadata['unique_statutes']} statutes"
            }

        except Exception as e:
            logger.error(f"Normalization failed: {e}")
            raise
    
    def _normalize_statute_name(self, name):
        """Normalize statute names"""
        if not name:
            return "UNKNOWN"
        
        # Convert to string and strip whitespace
        name = str(name).strip()
        
        # Remove extra whitespace and newlines
        name = re.sub(r'\s+', ' ', name)
        
        # Convert to title case
        name = name.title()
        
        # Remove special characters but keep spaces and basic punctuation
        name = re.sub(r'[^\w\s\-\.\(\)]', '', name)
        
        # Clean up multiple spaces again
        name = re.sub(r'\s+', ' ', name).strip()
        
        return name if name else "UNKNOWN"
    
    def _section_sort_key(self, section):
        """Returns a tuple for sorting sections"""
        num = section.get("Section", "")
        if isinstance(num, str) and num.strip().lower() == "preamble":
            return (0, "")
        
        # Try to parse as numeric
        try:
            num_str = num.strip() if isinstance(num, str) else str(num)
            if num_str.isdigit():
                return (1, int(num_str))
            else:
                return (1, float(num_str))
        except (ValueError, TypeError):
            pass
        
        # Not numeric, not preamble
        return (2, str(num).lower() if num else "")
            
    def cleanup(self):
        """Clean up service resources"""
        self.engine.cleanup()
