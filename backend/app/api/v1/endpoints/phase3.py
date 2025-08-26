from fastapi import APIRouter, HTTPException, BackgroundTasks, status
from pydantic import BaseModel, validator
import re
from typing import Dict, Any, List, Optional
from ....core.services import SectionSplittingService
import subprocess
import tempfile
import os
import sys
from pathlib import Path
import json
from datetime import datetime, date
from motor.motor_asyncio import AsyncIOMotorClient
import glob
from collections import Counter
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# Configuration model - updated to match CLI flow
class Phase3Config(BaseModel):
    source_database: str = "Statutes"
    source_collection: str = "normalized_statutes"
    target_database: str = "Batched-Statutes"
    target_collection_prefix: str = "batch_"
    batch_size: int = 10
    enable_ai_cleaning: bool = False

    @validator('target_collection_prefix')
    def validate_target_prefix(cls, v: str):
        if not isinstance(v, str) or not v:
            raise ValueError('target_collection_prefix must be a non-empty string')
        v_stripped = v.strip()
        # Allow only alpha-numeric, underscore and hyphen, length 1-50
        if not re.match(r'^[A-Za-z0-9_-]{1,50}$', v_stripped):
            raise ValueError('target_collection_prefix must match /^[A-Za-z0-9_-]{1,50}$/')
        # Disallow names that could conflict with system collections or start with $
        if v_stripped.startswith('$') or v_stripped.lower().startswith('system'):
            raise ValueError('target_collection_prefix cannot start with "$" or "system"')
        return v_stripped

# New models for batch cleaning
class BatchCleaningConfig(BaseModel):
    target_database: str = "Batched-Statutes"
    target_collection_prefix: str = "batch_"
    batch_numbers: Optional[List[int]] = None  # None means all batches
    clean_all: bool = True
    skip_preamble_dedup: bool = True

    @validator('target_collection_prefix')
    def validate_target_prefix_batch(cls, v: str):
        if not isinstance(v, str) or not v:
            raise ValueError('target_collection_prefix must be a non-empty string')
        v_stripped = v.strip()
        if not re.match(r'^[A-Za-z0-9_-]{1,50}$', v_stripped):
            raise ValueError('target_collection_prefix must match /^[A-Za-z0-9_-]{1,50}$/')
        if v_stripped.startswith('$') or v_stripped.lower().startswith('system'):
            raise ValueError('target_collection_prefix cannot start with "$" or "system"')
        return v_stripped
@router.post("/preview-splitting-metadata")
async def preview_splitting_metadata(config: Phase3Config):
    """Preview metadata for section splitting without running actual splitting"""
    try:
        client = AsyncIOMotorClient(MONGODB_URI)
        db = client[config.source_database]
        coll = db[config.source_collection]
        total_docs = await coll.count_documents({})
        
        # batch_size now means "number of batches to create"
        num_batches = config.batch_size or 10
        
        # Calculate how documents will be distributed across batches
        if num_batches > 0 and total_docs > 0:
            docs_per_batch = total_docs // num_batches
            remainder = total_docs % num_batches
            chunk_sizes = [docs_per_batch + (1 if i < remainder else 0) for i in range(num_batches)]
        else:
            chunk_sizes = []
            
        mock_results = {
            "total_processed": total_docs,
            "splits_created": num_batches,
            "chunk_sizes": chunk_sizes,
            "total_sections": 0,
            "avg_sections": 0,
            "database_distribution": {},
            "preamble_count": 0,
            "multi_section_count": 0,
            "section_distribution": {}
        }
        metadata_preview = generate_comprehensive_metadata("section_splitting", config.dict(), mock_results)
        return {
            "status": "success",
            "message": "Splitting metadata preview generated",
            "metadata_preview": metadata_preview,
            "estimated_documents": total_docs,
            "estimated_batches": num_batches,
            "requested_batches": num_batches,
            "chunk_sizes": chunk_sizes
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to preview splitting metadata",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )

@router.post("/preview-cleaning-metadata")
async def preview_cleaning_metadata(config: Phase3Config):
    """Preview metadata for field cleaning without running actual cleaning"""
    try:
        client = AsyncIOMotorClient(MONGODB_URI)
        db = client[config.target_database]
        # Assume all batches for preview
        coll_names = [name for name in await db.list_collection_names() if name.startswith(config.target_collection_prefix)]
        total_docs = 0
        for coll_name in coll_names:
            coll = db[coll_name]
            count = await coll.count_documents({})
            total_docs += count
        mock_results = {
            "total_processed": total_docs,
            "total_cleaned": total_docs,
            "total_unchanged": 0,
            "fields_dropped": {},
            "section_fields_dropped": {},
            "common_fields_moved": {},
            "text_fields_cleaned": {},
            "batch_details": {},
            "preamble_sections": 0,
            "definition_fields": 0,
            "citation_fields": 0
        }
        metadata_preview = generate_comprehensive_metadata("field_cleaning", config.dict(), mock_results)
        return {
            "status": "success",
            "message": "Cleaning metadata preview generated",
            "metadata_preview": metadata_preview,
            "estimated_documents": total_docs,
            "batches_to_process": coll_names
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to preview cleaning metadata",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )
# Constants - updated to match CLI scripts
MONGODB_URI = "mongodb://localhost:27017"
DEFAULT_SOURCE_DB = "Statutes"
DEFAULT_SOURCE_COLL = "normalized_statutes"
DEFAULT_TARGET_DB = "Batched-Statutes"
DEFAULT_TARGET_COLL_PREFIX = "batch_"
DEFAULT_BATCH_SIZE = 10

# Pakistani provinces from CLI script
PAKISTANI_PROVINCES = [
    'Azad Kashmir And Jammu', 'Balochistan', 'Federal', 'Khyber Pakhtunkhwa', 'Punjab', 'Sindh',
    # Include Gilgit-Baltistan variants and common spellings
    'Gilgit Baltistan', 'Gilgit-Baltistan', 'Gilgit and Baltistan', 'Northern Areas'
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
    def split_statutes_into_batches(statutes: List[Dict[str, Any]], num_batches: int) -> List[List[Dict[str, Any]]]:
        """Split statutes into a specified number of batches"""
        batches = []
        total = len(statutes)
        
        if num_batches <= 0 or total == 0:
            return [statutes] if statutes else []
        
        # Calculate documents per batch (distribute as evenly as possible)
        docs_per_batch = total // num_batches
        remainder = total % num_batches
        
        start_idx = 0
        for i in range(num_batches):
            # Add one extra document to first 'remainder' batches to distribute evenly
            batch_size = docs_per_batch + (1 if i < remainder else 0)
            if start_idx >= total:
                break
            
            end_idx = min(start_idx + batch_size, total)
            batch = statutes[start_idx:end_idx]
            if batch:  # Only add non-empty batches
                batches.append(batch)
            start_idx = end_idx
        
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
        sync_source_db = sync_client[source_db]
        sync_target_db = sync_client[target_database]
        
        source_coll = sync_source_db[source_collection]
        statutes = list(source_coll.find({}))
        
        # batch_size now means "number of batches to create"
        num_batches = batch_size
        batches = SectionSplittingEngine.split_statutes_into_batches(statutes, num_batches)
        batch_collections = []
        metadata = {
            "total_statutes_processed": len(statutes),
            "splits_created": len(batches),
            "splitting_stats": {
                "requested_batches": num_batches,
                "actual_batches_created": len(batches),
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
        
        # Use unified naming convention: {operation}-{database}-{collection}-{date}.{ext}
        operation = "split"
        database = target_database.lower().replace("_", "-")
        collection = target_prefix.lower().replace("_", "-")
        date_str = date.today().isoformat()
        meta_filename = f"{operation}-{database}-{collection}-{date_str}.json"
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
            except (ValueError, TypeError, ImportError):
                pass  # Date parsing failed, continue with other checks
        
        # Check for Pakistan mentions
        if "pakistan" in preamble.lower() or "pakistan" in statute_name.lower():
            return True
        
        # Check for Pakistani provinces (case-insensitive match)
        if province and isinstance(province, str):
            prov_norm = province.strip().lower()
            provinces_lower = {p.lower() for p in PAKISTANI_PROVINCES}
            # Exact match first
            if prov_norm in provinces_lower:
                return True
            # Fallback: substring matches for common tokens (gilgit, baltistan, azad)
            tokens = ['gilgit', 'baltistan', 'azad', 'khyber', 'punjab', 'sindh', 'balochistan', 'federal']
            if any(tok in prov_norm for tok in tokens):
                return True
        
        # Check for Gazette of Pakistan mentions
        if "gazette of pakistan" in preamble.lower():
            return True

        # If province didn't indicate Pakistan, check statute name/preamble for province tokens
        name_lower = (statute_name or "").lower()
        pre_lower = (preamble or "").lower()
        province_tokens = ['gilgit', 'baltistan', 'northern areas', 'azad']
        if any(tok in name_lower for tok in province_tokens) or any(tok in pre_lower for tok in province_tokens):
            return True

        return False
    
    @staticmethod
    def drop_unnecessary_fields(doc: Dict[str, Any]) -> Dict[str, Any]:
        """Drop fields that are not needed for processing"""
        # Fields to drop from top-level (based on reference scripts)
        FIELDS_TO_DROP = {"Source", "Category", "PDF_URL", "Blob_Url", "Statute_RAG_Content", "Statute_HTML"}
        # Fields to drop from within each section
        SECTION_FIELDS_TO_DROP = {"Statute_RAG_Content", "Statute_HTML", "PDF_URL", "Blob_Url"}

        # Work on a shallow copy
        cleaned = doc.copy()

        # Remove unwanted top-level fields
        for f in FIELDS_TO_DROP:
            if f in cleaned:
                cleaned.pop(f, None)

        # Clean sections if present
        if isinstance(cleaned.get("Sections"), list):
            new_sections = []
            for section in cleaned.get("Sections", []):
                if not isinstance(section, dict):
                    new_sections.append(section)
                    continue
                # Remove unwanted section-level fields
                for sf in SECTION_FIELDS_TO_DROP:
                    if sf in section:
                        section.pop(sf, None)
                # Normalize Content-like fields
                for content_field in ("Content", "Statute", "Text"):
                    if content_field in section and isinstance(section[content_field], str):
                        section[content_field] = FieldCleaningEngine.clean_text_field(section[content_field])
                new_sections.append(section)
            cleaned["Sections"] = new_sections

        # Normalize some top-level text fields
        for tfield in ("Statute_Name", "Preamble"):
            if tfield in cleaned and isinstance(cleaned[tfield], str):
                cleaned[tfield] = FieldCleaningEngine.clean_text_field(cleaned[tfield])

        return cleaned
    
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

        # Helper: determine if the single section is empty or contains only null/empty values
        def is_single_empty_section(secs):
            if not isinstance(secs, list) or len(secs) != 1:
                return False
            sec = secs[0]
            if not isinstance(sec, dict):
                return False
            for v in sec.values():
                if v not in (None, "", [], {}):
                    return False
            return True

        # Fields that should be moved into Sections[0] when the single section is empty
        SECTION_FIELDS = [
            "Section", "Definition", "Citations", "Statute", "Text", "Title", "Subsection", "Bookmark_ID"
        ]

        # Fields to remove from top level when moving
        FIELDS_TO_REMOVE = ["Source", "Category", "PDF_URL", "Blob_Url", "Statute_RAG_Content", "Statute_HTML"]

        if len(sections) == 1 and is_single_empty_section(sections):
            # Build a new section from top-level fields
            new_section = {}
            for field in SECTION_FIELDS:
                if field in doc:
                    new_section[field] = doc.pop(field)

            # Ensure Citations is a list if present but None
            if "Citations" in new_section and new_section.get("Citations") is None:
                new_section["Citations"] = []

            # If Section is missing, set as Preamble
            if "Section" not in new_section:
                new_section["Section"] = "Preamble"

            # Remove other unwanted top-level fields
            for field in FIELDS_TO_REMOVE:
                if field in doc:
                    doc.pop(field, None)

            # Replace sections array
            doc["Sections"] = [new_section]

        # Also normalize any text fields in sections and top-level
        if isinstance(doc.get("Sections"), list):
            for section in doc["Sections"]:
                if isinstance(section, dict):
                    for f in ("Content", "Statute", "Text"):
                        if f in section and isinstance(section[f], str):
                            section[f] = FieldCleaningEngine.clean_text_field(section[f])

        for tfield in ("Statute_Name", "Preamble"):
            if tfield in doc and isinstance(doc[tfield], str):
                doc[tfield] = FieldCleaningEngine.clean_text_field(doc[tfield])

        return doc
    
    @staticmethod
    def remove_preamble_duplicates(doc: Dict[str, Any]) -> Dict[str, Any]:
        """Remove duplicate preamble sections"""
        sections = doc.get("Sections", [])
        if not sections:
            return doc
        # Locate the canonical preamble text (first PREAMBLE section)
        preamble_text = None
        preamble_index = None
        for i, section in enumerate(sections):
            name = (section.get("Section") or "").strip().lower()
            if name == "preamble":
                # Prefer Content -> Statute -> Definition fields for text
                preamble_text = section.get("Content") or section.get("Statute") or section.get("Definition") or ""
                preamble_index = i
                break

        if not preamble_text:
            # Nothing to dedupe
            return doc


        # Normalize preamble text
        def _norm(s: str) -> str:
            return " ".join(s.split()).strip()

        preamble_text_norm = _norm(preamble_text)
        if not preamble_text_norm:
            return doc

        # Split preamble into candidate sentences/fragments for safe removal
        # Keep longer fragments to reduce accidental removals
        MIN_FRAG_LEN = 30
        frags = [f.strip() for f in re.split(r"[\.\n]\s*", preamble_text_norm) if len(f.strip()) >= MIN_FRAG_LEN]

        # Try to import RapidFuzz for fuzzy matching; fallback gracefully
        try:
            from rapidfuzz import fuzz
            _rapidfuzz_available = True
        except Exception:
            _rapidfuzz_available = False

        # Embedding fallback is disabled by default to avoid heavy model loads during dry-runs.
        EMBED_FALLBACK_ENABLED = False
        _embed_model = None
        _embed_available = False
        EMBED_MODEL_NAME = "all-MiniLM-L6-v2"
        EMBED_THRESHOLD = 0.78
        if EMBED_FALLBACK_ENABLED:
            try:
                # import utils only; model loading is delayed until needed
                from sentence_transformers import SentenceTransformer, util as _st_util
                _embed_available = True
            except Exception:
                _embed_available = False

        PARTIAL_THRESHOLD = 85
        TOKEN_SORT_THRESHOLD = 80
        cleaned_sections = []
        # collector for removed fragments to attach to doc for metadata
        preamble_removals = []  # list of {section_index, field, removed_fragments}
        for i, section in enumerate(sections):
            # Always keep the canonical preamble as-is (first occurrence)
            if i == preamble_index:
                cleaned_sections.append(section)
                continue

            # Work on a mutable copy of the section
            if not isinstance(section, dict):
                cleaned_sections.append(section)
                continue

            changed = False
            # Collect fragments to remove for this section to compile a single regex
            matched_frags = set()
            # Pre-split section into sentences/fragments for fuzzy checking
            sec_frag_candidates = []
            for content_field in ("Content", "Statute", "Definition"):
                if content_field in section and isinstance(section[content_field], str):
                    sec_text = _norm(section[content_field])
                    # split into sentences/newline fragments
                    sec_frag_candidates.extend([s.strip() for s in re.split(r"[\.\n]\s*", sec_text) if s.strip()])

            sec_lower = " \n".join(sec_frag_candidates).lower()

            for frag in frags:
                frag_lower = frag.lower()
                # fast substring check first
                if frag_lower in sec_lower:
                    matched_frags.add(frag)
                    continue
                # fallback to RapidFuzz fuzzy matching if available
                if _rapidfuzz_available and sec_frag_candidates:
                    best_partial = 0
                    best_token = 0
                    for cand in sec_frag_candidates:
                        # partial_ratio detects substring-like similarity
                        try:
                            pr = fuzz.partial_ratio(frag, cand)
                            if pr > best_partial:
                                best_partial = pr
                            tr = fuzz.token_sort_ratio(frag, cand)
                            if tr > best_token:
                                best_token = tr
                        except Exception:
                            # if RapidFuzz fails for a particular pair, skip
                            continue
                    if best_partial >= PARTIAL_THRESHOLD or best_token >= TOKEN_SORT_THRESHOLD:
                        matched_frags.add(frag)
                    else:
                        # If RapidFuzz was available but not decisive, optionally use embedding fallback
                        if _embed_available:
                            try:
                                if _embed_model is None:
                                    _embed_model = SentenceTransformer(EMBED_MODEL_NAME)
                                frag_emb = _embed_model.encode(frag, convert_to_tensor=True)
                                cand_embs = _embed_model.encode(sec_frag_candidates, convert_to_tensor=True)
                                sims = _st_util.cos_sim(frag_emb, cand_embs)[0]
                                max_sim = float(sims.max())
                                if max_sim >= EMBED_THRESHOLD:
                                    matched_frags.add(frag)
                            except Exception:
                                # If embeddings fail, skip
                                pass

            # If no fragments matched, keep section as-is
            if not matched_frags:
                cleaned_sections.append(section)
                continue

            # Now perform removals: compile a single alternation regex from matched fragments
            # Sort by length desc to prefer longer matches first
            to_remove = sorted(matched_frags, key=lambda s: -len(s))
            # avoid building an excessively long pattern
            MAX_PATTERN_CHARS = 20000
            pattern_parts = []
            total_len = 0
            for t in to_remove:
                esc = re.escape(t)
                total_len += len(esc)
                if total_len > MAX_PATTERN_CHARS:
                    break
                pattern_parts.append(esc)
            if not pattern_parts:
                cleaned_sections.append(section)
                continue
            pattern = re.compile("(" + "|".join(pattern_parts) + ")", flags=re.IGNORECASE)

            # Apply regex removal to each content field and normalize
            removed_for_section = []
            for content_field in ("Content", "Statute", "Definition"):
                if content_field in section and isinstance(section[content_field], str):
                    orig = _norm(section[content_field])
                    new_val = pattern.sub("", orig)
                    new_val = " ".join(new_val.split())
                    if new_val != orig:
                        section[content_field] = new_val
                        changed = True
                        # record which fragments were removed from this field
                        # include truncated fragment text for safety
                        for f in to_remove:
                            if re.search(re.escape(f), orig, flags=re.IGNORECASE):
                                removed_for_section.append({"field": content_field, "fragment": f if len(f) <= 200 else f[:200] + "..."})
            if removed_for_section:
                preamble_removals.append({"section_index": i, "removed": removed_for_section})
            # If all main content fields are now empty, skip adding this section
            has_content = any(
                isinstance(section.get(f), str) and section.get(f).strip() for f in ("Content", "Statute", "Definition")
            )
            if has_content:
                cleaned_sections.append(section)
            else:
                # Section became empty after removal; drop it
                pass

        doc["Sections"] = cleaned_sections
        if preamble_removals:
            # attach transient metadata on the doc so callers can record it in their metadata
            doc["_preamble_fragment_removals"] = preamble_removals
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
            except ValueError:
                # Text sections last
                return (2, 0, section_name)
        
        sorted_sections = sorted(sections, key=section_sort_key)
        doc["Sections"] = sorted_sections
        return doc
    
    @staticmethod
    def clean_document_structure(doc: Dict[str, Any]) -> Dict[str, Any]:
        """Apply all cleaning steps to a document"""
    # NOTE: cleaning should NOT drop documents. Dropping non-Pakistan or pre-1947
    # statutes is handled exclusively by the validation endpoint
    # (/validate-pakistan-batches). Here we only perform non-destructive
    # field-cleaning operations and return the cleaned document.

    # Apply cleaning steps (do not early-return or delete)
        cleaned = FieldCleaningEngine.drop_unnecessary_fields(doc)
        cleaned = FieldCleaningEngine.bring_common_fields_up(cleaned)
        cleaned = FieldCleaningEngine.clean_single_section_statutes(cleaned)
        cleaned = FieldCleaningEngine.remove_preamble_duplicates(cleaned)
        cleaned = FieldCleaningEngine.sort_sections_within_statutes(cleaned)

        # Add cleaning metadata
        cleaned["cleaned_at"] = datetime.now().isoformat()
        cleaned["cleaning_version"] = "1.0"

        return cleaned

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
        
        files = glob.glob(os.path.join(metadata_dir, "*.json"))
        # Filter for metadata files (both old and new naming conventions)
        metadata_files = [f for f in files if (
            os.path.basename(f).startswith("metadata_") or  # Old convention
            any(os.path.basename(f).startswith(prefix) for prefix in ["split-", "cleaning-", "generated-", "pakistan-", "normalize-", "merge-"])  # New convention
        )]
        metadata_list = []
        
        for file_path in sorted(metadata_files, reverse=True):  # Most recent first
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
        
        # Generate filename with batch info using unified naming convention
        batch_suffix = "all" if config.clean_all else f"batches-{'_'.join(map(str, config.batch_numbers))}"
        operation = "cleaning"
        database = config.target_database.lower().replace("_", "-")
        collection = config.target_collection_prefix.lower().replace("_", "-")
        date_str = date.today().isoformat()
        meta_filename = f"{operation}-{database}-{collection}-{batch_suffix}-{date_str}.json"
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

@router.post("/process-statute")
async def process_statute_with_service(statute_data: Dict[str, Any]):
    """
    Process a single statute using the new SectionSplittingService.
    
    This demonstrates the cleaner service-based approach for section splitting.
    """
    try:
        # Initialize service
        service = SectionSplittingService()
        
        # Process the statute
        result = service.process_statute(statute_data)
        
        # Validate the result
        validation = service.validate_processing_result(result)
        
        logger.info(f"Processed statute with {len(result.get('sections', []))} sections")
        
        return {
            "success": True,
            "message": "Statute processed successfully",
            "data": result,
            "validation": validation,
            "timestamp": datetime.now().isoformat()
        }
        
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Invalid statute data",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )
    except Exception as e:
        logger.error(f"Section splitting service error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Processing failed",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )

@router.post("/start-section-splitting-legacy")
async def start_section_splitting_legacy(config: Phase3Config):
    """
    DEPRECATED: Legacy section splitting endpoint.
    This endpoint has been moved for backward compatibility.
    Use /process-statute instead for new implementations.
    """
    return {
        "success": False,
        "error": "DEPRECATED_ENDPOINT",
        "message": "This endpoint has been deprecated. Use /process-statute instead.",
        "migration_guide": {
            "old_endpoint": "/start-section-splitting",
            "new_endpoint": "/process-statute",
            "status": "The new endpoint provides better service architecture and performance"
        },
        "timestamp": datetime.now().isoformat()
    }

@router.post("/start-section-splitting")
async def start_section_splitting(config: Phase3Config):
    """
    Start section splitting process using the SectionSplittingService.
    
    This endpoint maintains backward compatibility while delegating to the modern
    service-based architecture for better performance and maintainability.
    """
    try:
        logger.info("🔄 Executing section splitting using real batch logic...")
        # Use the real batch splitting function
        batch_collections, metadata = SectionSplittingEngine.create_batch_collections(
            source_db=config.source_database,
            target_db=config.target_database,
            batch_size=config.batch_size,
            source_collection=config.source_collection,
            target_database=config.target_database,
            target_prefix=config.target_collection_prefix
        )
        response = {
            "status": "success",
            "message": f"Section splitting completed: {len(batch_collections)} batches created.",
            "batches_created": len(batch_collections),
            "batch_collections": batch_collections,
            "metadata": metadata,
            "metadata_file": metadata.get("metadata_file"),
            "config": config.dict()
        }
        logger.info(f"✅ Section splitting completed: {len(batch_collections)} batches created.")
        return response
    except Exception as e:
        logger.error(f"❌ Section splitting failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Section splitting failed",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )

@router.post("/start-field-cleaning")
async def start_field_cleaning(config: Phase3Config):
    """Start field cleaning across all batch collections (runs in background)."""
    try:
        logger.info("🔄 Scheduling field cleaning for Phase 3 batches...")

        client = AsyncIOMotorClient(MONGODB_URI)
        db = client[config.target_database]

        # Determine batch collection names
        batch_collections = [name for name in await db.list_collection_names()
                             if name.startswith(config.target_collection_prefix)]

        # Prepare batch cleaning config
        cleaning_config = BatchCleaningConfig(
            target_database=config.target_database,
            target_collection_prefix=config.target_collection_prefix,
            batch_numbers=None,
            clean_all=True
        )

        # Run in background via asyncio.create_task so the endpoint returns immediately
        import asyncio
        asyncio.create_task(execute_batch_cleaning(cleaning_config, batch_collections))

        return {
            "status": "success",
            "message": f"Field cleaning scheduled for {len(batch_collections)} batches",
            "batches_scheduled": batch_collections,
            "config": config.dict()
        }
    except Exception as e:
        logger.error(f"❌ Scheduling field cleaning failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Scheduling field cleaning failed",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }
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
            
            # Add section details for each document
            for doc in sample_docs_serialized:
                if "Sections" in doc and doc["Sections"]:
                    doc["section_details"] = []
                    for section in doc["Sections"]:
                        section_detail = {
                            "section_number": section.get("Section", "Unknown"),
                            "section_title": section.get("Section", "Unknown"),
                            "content": section.get("Content", section.get("definition", "No content available")),
                            "content_preview": (section.get("Content", section.get("definition", ""))[:200] + "..." 
                                              if len(section.get("Content", section.get("definition", ""))) > 200 
                                              else section.get("Content", section.get("definition", "No content available")))
                        }
                        doc["section_details"].append(section_detail)
            
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
        
        # Use unified naming convention: {operation}-{database}-{collection}-{date}.{ext}
        operation = "generated"
        database = config.target_database.lower().replace("_", "-")
        collection = config.target_collection_prefix.lower().replace("_", "-")
        date_str = date.today().isoformat()
        meta_filename = f"{operation}-{database}-{collection}-{date_str}.json"
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
async def clean_selected_batches(config: BatchCleaningConfig):
    """Clean selected batches (or all if none specified). Runs asynchronously in background."""
    try:
        logger.info("🔄 Scheduling selected batch cleaning...")
        client = AsyncIOMotorClient(MONGODB_URI)
        db = client[config.target_database]

        # Determine which collections to process
        if config.batch_numbers:
            coll_names = [f"{config.target_collection_prefix}{n}" for n in config.batch_numbers]
        else:
            coll_names = [name for name in await db.list_collection_names()
                          if name.startswith(config.target_collection_prefix)]

        # Prepare cleaning config
        cleaning_config = config

        import asyncio
        asyncio.create_task(execute_batch_cleaning(cleaning_config, coll_names))

        return {
            "status": "success",
            "message": f"Scheduled cleaning for {len(coll_names)} batches",
            "batches_scheduled": coll_names,
            "config": config.dict()
        }
    except Exception as e:
        logger.error(f"❌ Scheduling selected batch cleaning failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Scheduling selected batch cleaning failed",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )

@router.post("/preview-validation-metadata")
async def preview_validation_metadata(config: BatchCleaningConfig, dry_run: bool = True):
    """Preview validation metadata without running actual validation"""
    try:
        client = AsyncIOMotorClient(MONGODB_URI)
        db = client[config.target_database]
        
        # Determine which batch collections to process
        if config.batch_numbers:
            coll_names = [f"{config.target_collection_prefix}{n}" for n in config.batch_numbers]
        else:
            coll_names = [name for name in await db.list_collection_names()
                          if name.startswith(config.target_collection_prefix)]
        
        # Get basic statistics without processing
        total_docs = 0
        for coll_name in coll_names:
            coll = db[coll_name]
            count = await coll.count_documents({})
            total_docs += count
        
        # Create mock validation results for metadata preview
        mock_results = {
            "total_scanned": total_docs,
            "total_dropped": 0,  # Will be determined during actual validation
            "total_kept": total_docs,  # Assuming all kept for preview
            "processed_batches": len(coll_names),
            "dropped_docs": [],
            "kept_docs": [],
            "dry_run": True
        }
        
        # Generate metadata preview
        metadata_preview = generate_validation_metadata(mock_results, config, dry_run)
        
        return {
            "status": "success",
            "message": "Metadata preview generated",
            "metadata_preview": metadata_preview,
            "estimated_documents": total_docs,
            "batches_to_process": coll_names
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to preview validation metadata",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }
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
            
            # Check if already cleaned (accept both legacy and current markers)
            cleaned_count = await batch_coll.count_documents({
                "$or": [
                    {"field_cleaned_at": {"$exists": True}},
                    {"cleaned_at": {"$exists": True}},
                ]
            })
            
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


@router.post("/batch-diagnostics")
async def batch_diagnostics(config: Phase3Config):
    """Return diagnostic info for each batch collection to help debug cleaning markers
    Reports counts for legacy marker `field_cleaned_at`, new `cleaned_at`, and total docs.
    """
    try:
        client = AsyncIOMotorClient(MONGODB_URI)
        target_db = client[config.target_database]

        batch_collections = [name for name in await target_db.list_collection_names()
                              if name.startswith(config.target_collection_prefix)]

        diagnostics = []
        for batch_name in batch_collections:
            coll = target_db[batch_name]
            total = await coll.count_documents({})
            legacy = await coll.count_documents({"field_cleaned_at": {"$exists": True}})
            modern = await coll.count_documents({"cleaned_at": {"$exists": True}})
            any_clean = await coll.count_documents({
                "$or": [{"field_cleaned_at": {"$exists": True}}, {"cleaned_at": {"$exists": True}}]
            })
            # Grab small sample ids for each marker type
            legacy_samples = [str(d.get("_id")) for d in await coll.find({"field_cleaned_at": {"$exists": True}}, {"_id": 1}).limit(5).to_list(None)]
            modern_samples = [str(d.get("_id")) for d in await coll.find({"cleaned_at": {"$exists": True}}, {"_id": 1}).limit(5).to_list(None)]

            diagnostics.append({
                "batch_name": batch_name,
                "total_documents": total,
                "legacy_cleaned_count": legacy,
                "modern_cleaned_count": modern,
                "any_cleaned_count": any_clean,
                "legacy_samples": legacy_samples,
                "modern_samples": modern_samples
            })

        return {"status": "success", "batches": diagnostics}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

def generate_validation_metadata(validation_results: Dict[str, Any], config: BatchCleaningConfig, dry_run: bool) -> Dict[str, Any]:
    """Generate comprehensive metadata for Pakistan law validation following reference patterns"""
    from collections import Counter
    
    # Analyze drop reasons
    drop_reasons = Counter()
    batch_stats = {}
    province_distribution = Counter()
    date_analysis = {"pre_1947": 0, "post_1947": 0, "no_date": 0}
    
    for doc in validation_results.get("dropped_docs", []):
        drop_reasons[doc["reason"]] += 1
        batch = doc["batch"]
        if batch not in batch_stats:
            batch_stats[batch] = {"dropped": 0, "kept": 0}
        batch_stats[batch]["dropped"] += 1
    
    for doc in validation_results.get("kept_docs", []):
        batch = doc["batch"]
        if batch not in batch_stats:
            batch_stats[batch] = {"dropped": 0, "kept": 0}
        batch_stats[batch]["kept"] += 1
    
    metadata = {
        "operation_type": "pakistan_law_validation",
        "total_statutes_processed": validation_results.get("total_scanned", 0),
        "validation_results": {
            "total_dropped": validation_results.get("total_dropped", 0),
            "total_kept": validation_results.get("total_kept", 0),
            "drop_rate": (validation_results.get("total_dropped", 0) / validation_results.get("total_scanned", 1)) * 100,
            "keep_rate": (validation_results.get("total_kept", 0) / validation_results.get("total_scanned", 1)) * 100
        },
        "drop_reason_analysis": {
            "reason_distribution": dict(drop_reasons),
            "top_drop_reasons": drop_reasons.most_common(5),
            "reason_percentages": {
                reason: (count / validation_results.get("total_dropped", 1)) * 100 
                for reason, count in drop_reasons.items()
            }
        },
        "batch_distribution": {
            "batches_processed": validation_results.get("processed_batches", 0),
            "batch_stats": batch_stats,
            "batch_effectiveness": {
                batch: {
                    "total": stats["dropped"] + stats["kept"],
                    "drop_rate": (stats["dropped"] / (stats["dropped"] + stats["kept"])) * 100 if (stats["dropped"] + stats["kept"]) > 0 else 0
                }
                for batch, stats in batch_stats.items()
            }
        },
        "processing_details": {
            "dry_run": dry_run,
            "target_database": config.target_database,
            "target_collection_prefix": config.target_collection_prefix,
            "batch_numbers": config.batch_numbers,
            "validation_method": "rule_based_with_gpt_fallback",
            "processing_date": date.today().isoformat(),
            "processing_timestamp": datetime.now().isoformat()
        },
        "validation_methodology": {
            "rule_based_checks": [
                "pre_1947_date_check",
                "foreign_country_keywords",
                "pakistan_mentions",
                "pakistani_provinces",
                "gazette_of_pakistan"
            ],
            "gpt_fallback": True,
            "confidence_level": "high" if validation_results.get("total_scanned", 0) > 100 else "medium"
        },
        "script": "api_phase3_pakistan_validation",
        "db_name": config.target_database,
        "collection": config.target_collection_prefix
    }
    
    return metadata

@router.post("/validate-pakistan-batches")
async def validate_pakistan_batches(config: BatchCleaningConfig, dry_run: bool = False, save_metadata: bool = True):
    """Validate batches by dropping non-Pakistan laws in each batch collection. If dry_run, only preview drops."""
    try:
        client = AsyncIOMotorClient(MONGODB_URI)
        db = client[config.target_database]
        # Determine which batch collections to process
        if config.batch_numbers:
            coll_names = [f"{config.target_collection_prefix}{n}" for n in config.batch_numbers]
        else:
            coll_names = [name for name in await db.list_collection_names()
                          if name.startswith(config.target_collection_prefix)]
        service = SectionSplittingService()
        total_scanned = total_dropped = total_kept = 0
        dropped_docs = []
        kept_docs = []
        for coll_name in coll_names:
            coll = db[coll_name]
            async for doc in coll.find({}):
                total_scanned += 1
                val_result = service.validate_pakistan_law_only(doc)
                display_name = doc.get("Statute_Name") or str(doc.get("_id"))
                # Map backend reason to concise, human-readable reason
                backend_reason = val_result.get("reason", "Unknown reason")
                if "pre-1947" in backend_reason.lower():
                    drop_reason = "Pre-1947"
                elif "foreign" in backend_reason.lower():
                    drop_reason = "Foreign statute"
                elif "rule-based check failed" in backend_reason.lower():
                    drop_reason = "Rule-based failed"
                elif "gpt" in backend_reason.lower():
                    drop_reason = "AI/GPT flagged"
                else:
                    drop_reason = backend_reason
                if not val_result["is_pakistan_law"]:
                    total_dropped += 1
                    dropped_docs.append({
                        "name": display_name,
                        "reason": drop_reason,
                        "batch": coll_name
                    })
                    if not dry_run:
                        await coll.delete_one({"_id": doc.get("_id")})
                else:
                    total_kept += 1
                    kept_docs.append({
                        "name": display_name,
                        "batch": coll_name
                    })
        
        validation_results = {
            "total_scanned": total_scanned,
            "total_dropped": total_dropped,
            "total_kept": total_kept,
            "processed_batches": len(coll_names),
            "dropped_docs": dropped_docs,
            "kept_docs": kept_docs,
            "dry_run": dry_run
        }
        
        # Generate and optionally save metadata
        metadata = None
        metadata_file = None
        if save_metadata:
            metadata = generate_validation_metadata(validation_results, config, dry_run)
            metadata_file = save_validation_metadata(metadata, config, dry_run)
        
        return {
            "status": "success",
            "message": f"Pakistan validation completed",
            **validation_results,
            "metadata": metadata,
            "metadata_file": metadata_file
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Pakistan batch validation failed",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )

def save_operation_metadata(metadata: Dict[str, Any], operation_type: str, config: Dict[str, Any], collection_names: Optional[List[str]] = None) -> str:
    """Save operation metadata to file following reference patterns"""
    metadata_dir = MetadataManager.get_metadata_directory()
    os.makedirs(metadata_dir, exist_ok=True)
    
    # Generate filename with operation info
    target_db = config.get("target_database", "unknown")
    # Prefer explicit collection names when provided, otherwise fall back to prefix
    if collection_names:
        coll_part = "_".join(collection_names)
    else:
        coll_part = config.get("target_collection_prefix", "unknown")
    # sanitize coll_part a bit (remove trailing underscores)
    coll_part = coll_part.rstrip("_")
    
    # Use unified naming convention: {operation}-{database}-{collection}-{date}.{ext}
    database = target_db.lower().replace("_", "-")
    collection = coll_part.lower().replace("_", "-")
    date_str = date.today().isoformat()
    meta_filename = f"{operation_type}-{database}-{collection}-{date_str}.json"
    meta_path = os.path.join(metadata_dir, meta_filename)
    
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    return meta_filename

def save_validation_metadata(metadata: Dict[str, Any], config: BatchCleaningConfig, dry_run: bool) -> str:
    """Save validation metadata to file following reference patterns"""
    metadata_dir = MetadataManager.get_metadata_directory()
    os.makedirs(metadata_dir, exist_ok=True)
    
    # Generate filename with validation info using unified naming convention
    operation_type = "dry-run" if dry_run else "validation"
    batch_suffix = "all" if not config.batch_numbers else f"batches-{'_'.join(map(str, config.batch_numbers))}"
    database = config.target_database.lower().replace("_", "-")
    collection = config.target_collection_prefix.lower().replace("_", "-")
    date_str = date.today().isoformat()
    meta_filename = f"pakistan-{operation_type}-{database}-{collection}-{batch_suffix}-{date_str}.json"
    meta_path = os.path.join(metadata_dir, meta_filename)
    
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    return meta_filename

def generate_comprehensive_metadata(operation_type: str, config: Dict[str, Any], results: Dict[str, Any]) -> Dict[str, Any]:
    """Generate comprehensive metadata for any Phase 3 operation following reference patterns"""
    from collections import Counter
    
    base_metadata = {
        "operation_type": operation_type,
        "total_statutes_processed": results.get("total_processed", 0),
        "processing_details": {
            "processing_date": date.today().isoformat(),
            "processing_timestamp": datetime.now().isoformat(),
            "script": f"api_phase3_{operation_type}",
            "configuration": config
        }
    }
    
    # Add operation-specific metadata
    if operation_type == "section_splitting":
        base_metadata.update({
            "splits_created": results.get("splits_created", 0),
            "splitting_stats": {
                "base_chunk_size": config.get("batch_size", 0),
                "chunk_sizes": results.get("chunk_sizes", []),
                "total_sections_distributed": results.get("total_sections", 0),
                "average_sections_per_statute": results.get("avg_sections", 0)
            },
            "database_distribution": results.get("database_distribution", {}),
            "content_analysis": {
                "statutes_with_preamble": results.get("preamble_count", 0),
                "statutes_with_multiple_sections": results.get("multi_section_count", 0),
                "section_count_distribution": results.get("section_distribution", {})
            }
        })
    
    elif operation_type == "field_cleaning":
        base_metadata.update({
            "cleaning_stats": {
                "total_cleaned": results.get("total_cleaned", 0),
                "total_unchanged": results.get("total_unchanged", 0),
                "fields_dropped_count": results.get("fields_dropped", {}),
                "section_fields_dropped_count": results.get("section_fields_dropped", {}),
                "common_fields_moved_count": results.get("common_fields_moved", {}),
                "text_fields_cleaned_count": results.get("text_fields_cleaned", {})
            },
            "batch_details": results.get("batch_details", {}),
            "field_analysis": {
                "statutes_with_preamble_section": results.get("preamble_sections", 0),
                "statutes_with_definition_field": results.get("definition_fields", 0),
                "statutes_with_citations_field": results.get("citation_fields", 0)
            }
        })
    elif operation_type == "batch_cleaning":
        fm = results.get("field_modifications", {})
        # Build structured field modifications summary
        field_mod_summary = {
            "summary": {
                "total_fields_processed": fm.get("total_fields_processed", 0),
                "fields_dropped": fm.get("fields_dropped", 0),
                "fields_moved": fm.get("fields_moved", 0)
            },
            "detailed_changes": fm.get("detailed_changes", [])
        }
        base_metadata.update({
            "cleaning_stats": {
                "total_cleaned": results.get("total_cleaned", 0),
                "total_unchanged": results.get("total_unchanged", 0)
            },
            "batch_details": results.get("batch_details", {}),
            "field_modifications": field_mod_summary
        })
    
    return base_metadata

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
            "batch_details": {},
            # New detailed tracking
            "fields_dropped_total": 0,
            "fields_moved_total": 0,
            "detailed_changes": []  # list of {field_name, change_type, original_position, new_position, doc_id, batch}
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
                # If configured, skip the preamble deduplication step
                if getattr(config, 'skip_preamble_dedup', False):
                    cleaned = FieldCleaningEngine.drop_unnecessary_fields(doc)
                    cleaned = FieldCleaningEngine.bring_common_fields_up(cleaned)
                    cleaned = FieldCleaningEngine.clean_single_section_statutes(cleaned)
                    # skip remove_preamble_duplicates when flag is set
                    cleaned = FieldCleaningEngine.sort_sections_within_statutes(cleaned)
                    # Add cleaning metadata
                    cleaned["cleaned_at"] = datetime.now().isoformat()
                    cleaned["cleaning_version"] = "1.0"
                    cleaned_doc = cleaned
                else:
                    cleaned_doc = FieldCleaningEngine.clean_document_structure(doc)

                # Compute field-level changes between original and cleaned doc
                def compute_field_changes(original: Dict[str, Any], cleaned: Dict[str, Any], batch_name: str):
                    changes = []

                    # Top-level key order
                    orig_keys = list(original.keys())
                    cleaned_keys = list(cleaned.keys())

                    # Helper: collect all field names present in original sections
                    orig_section_fields = []  # tuples (section_index, field_name)
                    if isinstance(original.get("Sections"), list):
                        for si, sec in enumerate(original.get("Sections", [])):
                            if isinstance(sec, dict):
                                for fk in sec.keys():
                                    orig_section_fields.append((si, fk))

                    # Determine moved fields: those that appear at top-level in cleaned but only in sections in original
                    moved_field_names = set()
                    for k in cleaned_keys:
                        if k not in orig_keys:
                            # if present in original sections, consider moved
                            if any(fk == k for (_si, fk) in orig_section_fields):
                                moved_field_names.add(k)

                    # Dropped top-level fields (or moved into sections)
                    for k in orig_keys:
                        if k not in cleaned_keys:
                            # If this key was moved into a section in the cleaned doc, record as moved_to_section
                            moved_to_section = False
                            if isinstance(cleaned.get("Sections"), list):
                                for si, sec in enumerate(cleaned.get("Sections")):
                                    if isinstance(sec, dict) and k in sec:
                                        moved_to_section = True
                                        changes.append({
                                            "field_name": k,
                                            "change_type": "moved_to_section",
                                            "original_position": orig_keys.index(k),
                                            "new_position": si,
                                            "doc_id": str(original.get("_id")),
                                            "batch": batch_name
                                        })
                                        break
                            if not moved_to_section:
                                # Otherwise mark dropped
                                changes.append({
                                    "field_name": k,
                                    "change_type": "dropped",
                                    "original_position": orig_keys.index(k),
                                    "new_position": None,
                                    "doc_id": str(original.get("_id")),
                                    "batch": batch_name
                                })

                    # Dropped section fields (that were not moved to top-level)
                    for si, fk in orig_section_fields:
                        # If that field is no longer present in the same section index in cleaned, and not moved
                        still_in_section = False
                        if isinstance(cleaned.get("Sections"), list) and si < len(cleaned.get("Sections")):
                            sec = cleaned.get("Sections")[si]
                            if isinstance(sec, dict) and fk in sec:
                                still_in_section = True
                        if not still_in_section and fk not in moved_field_names:
                            changes.append({
                                "field_name": fk,
                                "change_type": "dropped",
                                "original_position": si,
                                "new_position": None,
                                "doc_id": str(original.get("_id")),
                                "batch": batch_name
                            })

                    # Moved fields: record original section index (first occurrence) and new top-level index
                    for fname in moved_field_names:
                        # find first section index where it existed
                        orig_pos = None
                        for si, fk in orig_section_fields:
                            if fk == fname:
                                orig_pos = si
                                break
                        new_pos = cleaned_keys.index(fname) if fname in cleaned_keys else None
                        changes.append({
                            "field_name": fname,
                            "change_type": "moved",
                            "original_position": orig_pos,
                            "new_position": new_pos,
                            "doc_id": str(original.get("_id")),
                            "batch": batch_name
                        })

                    return changes

                # Only compute diffs if cleaned_doc is a dict
                if isinstance(cleaned_doc, dict):
                    doc_changes = compute_field_changes(doc, cleaned_doc, batch_name)
                    # record preamble fragment removals if present
                    if cleaned_doc.get("_preamble_fragment_removals"):
                        for rem in cleaned_doc.get("_preamble_fragment_removals", []):
                            sec_idx = rem.get("section_index")
                            for entry in rem.get("removed", []):
                                cleaning_stats["detailed_changes"].append({
                                    "field_name": entry.get("field"),
                                    "change_type": "preamble_fragment_removed",
                                    "original_position": sec_idx,
                                    "fragment": entry.get("fragment"),
                                    "doc_id": str(doc.get("_id")),
                                    "batch": batch_name
                                })
                    if doc_changes:
                        cleaning_stats["detailed_changes"].extend(doc_changes)
                        # Update totals
                        for ch in doc_changes:
                            if ch["change_type"] == "dropped":
                                cleaning_stats["fields_dropped_total"] += 1
                                cleaning_stats["fields_dropped_count"][ch["field_name"]] += 1
                            elif ch["change_type"] in ("moved", "moved_to_section"):
                                # Treat moved_to_section as a move for summary purposes
                                cleaning_stats["fields_moved_total"] += 1
                                cleaning_stats["common_fields_moved_count"][ch["field_name"]] += 1
                
                if cleaned_doc is None:
                    # NOTE: cleaning should not delete documents. If the cleaning engine
                    # previously returned None (indicating a drop), we now preserve the
                    # document and mark it unchanged; actual drops are handled by
                    # /validate-pakistan-batches.
                    batch_unchanged += 1
                    cleaning_stats["total_unchanged"] += 1
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
        
        # Save metadata using the comprehensive metadata system
        batch_cleaning_metadata = generate_comprehensive_metadata(
            "batch_cleaning",
            config.dict(),
            {
                "total_processed": cleaning_stats["total_processed"],
                "total_cleaned": cleaning_stats["total_cleaned"],
                "total_unchanged": cleaning_stats["total_unchanged"],
                "fields_dropped": dict(cleaning_stats["fields_dropped_count"]),
                "section_fields_dropped": dict(cleaning_stats["section_fields_dropped_count"]),
                "common_fields_moved": dict(cleaning_stats["common_fields_moved_count"]),
                "text_fields_cleaned": dict(cleaning_stats["text_fields_cleaned_count"]),
                "batch_details": cleaning_stats["batch_details"],
                # New field modification summary
                "field_modifications": {
                    "total_fields_processed": cleaning_stats["total_processed"],
                    "fields_dropped": cleaning_stats["fields_dropped_total"],
                    "fields_moved": cleaning_stats["fields_moved_total"],
                    "detailed_changes": cleaning_stats["detailed_changes"]
                },
                "preamble_sections": 0,
                "definition_fields": 0,
                "citation_fields": 0
            }
        )

        # Pass the concrete batch names so the metadata filename reflects the exact collections processed
        metadata_path = save_operation_metadata(batch_cleaning_metadata, "batch_cleaning", config.dict(), collection_names=batches_to_clean)
        print(f"Batch cleaning completed. Metadata saved to: {metadata_path}")

    except Exception as e:
        print(f"Error in batch cleaning: {str(e)}")
