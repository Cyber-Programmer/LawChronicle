import os
import json
import asyncio
import logging
import re
import unicodedata
import traceback
from typing import AsyncGenerator, Dict, Any, List, Optional, Tuple
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
from bson import ObjectId
from collections import defaultdict
from pathlib import Path
from openai import AzureOpenAI
from pydantic import BaseModel, ValidationError

from shared.types.common import (
    Phase5Config, 
    StatuteGroup, 
    NestedStatute,
    StatuteSection,
    ProcessingResult
)

logger = logging.getLogger(__name__)


def convert_objectids_to_strings(obj):
    """Recursively convert ObjectId instances to strings in a dictionary or list."""
    if isinstance(obj, ObjectId):
        return str(obj)
    elif isinstance(obj, dict):
        return {key: convert_objectids_to_strings(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_objectids_to_strings(item) for item in obj]
    else:
        return obj


class GPTGroupingRequest(BaseModel):
    groups: List[List[int]]
    relations: Dict[str, Dict[str, Any]]
    similarity: Dict[str, float]


class Phase5Service:
    """Service for Phase 5: Contextual Statute Grouping and Versioning
    
    Groups statutes based on preamble + early sections semantics using Azure GPT-4o.
    Creates nested group documents with proper versioning and relation detection.
    Operates independently without cross-phase dependencies.
    """
    
    def __init__(self):
        # MongoDB connection
        self.mongo_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
        self.client = AsyncIOMotorClient(self.mongo_url)
        
        # Default configuration
        self.default_config = Phase5Config()
        
        # Processing control
        self._should_stop = False
        self._current_progress = 0.0
        
        # Initialize Azure OpenAI client
        self.azure_openai_client = None
        self.deployment_name = None
        self._init_azure_openai()
        
        # System prompt for GPT
        self.system_prompt = """You are a senior Pakistani legal analyst. Group statutes that share the same base legal instrument based on their context (preamble + early sections), not just their names.

Rules (must-follow):
1) Never group across different provinces/jurisdictions.
2) Prefer semantic equivalence over title similarity; if content indicates the same underlying law, group them.
3) Within each group, identify the original (oldest by year if context confirms same base law). Others label as amendment/ordinance/repeal/supplement as appropriate; if unclear, use "unknown".
4) Ignore stylistic differences (punctuation, commas, "Act" vs "Act, 1975", casing).
5) Prefer constitutional context understanding (e.g., "Constitution of Pakistan" vs "Constitution (Amendment) Order").
6) Output machine-readable JSON only; no commentary."""

    def _init_azure_openai(self):
        """Initialize Azure OpenAI client from config file and environment variables."""
        try:
            # First try to load from config file
            config_path = os.path.join(os.path.dirname(__file__), "../../config/azure_openai_config.json")
            
            api_key = None
            endpoint = None
            api_version = "2024-02-15-preview"
            
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    azure_config = config.get("azure_openai", {})
                    api_key = azure_config.get("api_key")
                    endpoint = azure_config.get("endpoint")
                    api_version = azure_config.get("api_version", api_version)
                    self.deployment_name = azure_config.get("deployment_name", "gpt-4o")
                    logger.info(f"Loaded configuration from {config_path}")
            
            # Fallback to environment variables if config file doesn't have values
            if not api_key:
                api_key = os.getenv("AZURE_OPENAI_API_KEY")
            if not endpoint:
                endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
            if not hasattr(self, 'deployment_name') or not self.deployment_name:
                self.deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
            
            if api_key and endpoint:
                self.azure_openai_client = AzureOpenAI(
                    api_key=api_key,
                    api_version=api_version,
                    azure_endpoint=endpoint
                )
                logger.info("Azure OpenAI client initialized from config file")
            else:
                logger.warning("Azure OpenAI credentials not found - falling back to rule-based grouping")
                
        except Exception as e:
            logger.error(f"Failed to initialize Azure OpenAI client: {e}")
            self.azure_openai_client = None

    async def _autodetect_source_collection(self, config: Phase5Config) -> Tuple[str, str]:
        """Autodetect source database and collection if not provided."""
        if config.source_database and config.source_collection:
            return config.source_database, config.source_collection
        
        # Try in order: Date-Enriched-Batches, Batched-Statutes, Statutes
        candidates = [
            ("Date-Enriched-Batches", ["batch_1", "batch_2", "batch_3", "batch_4", "batch_5", 
                                       "batch_6", "batch_7", "batch_8", "batch_9", "batch_10"]),
            ("Batched-Statutes", ["batch_1", "batch_2", "batch_3", "batch_4", "batch_5"]),
            ("Statutes", ["normalized_statutes"])
        ]
        
        for db_name, collection_names in candidates:
            try:
                db = self.client.get_database(db_name)
                for collection_name in collection_names:
                    count = await db[collection_name].count_documents({})
                    if count > 0:
                        logger.info(f"Autodetected source: {db_name}.{collection_name} ({count} documents)")
                        return db_name, collection_name
            except Exception as e:
                logger.debug(f"Could not access {db_name}: {e}")
                continue
        
        raise ValueError("No suitable source collection found. Please specify source_database and source_collection.")

    async def _fetch_statutes(self, config: Phase5Config) -> List[Dict[str, Any]]:
        """Fetch all statutes from the configured source collection."""
        source_db_name, source_collection_name = await self._autodetect_source_collection(config)
        source_db = self.client.get_database(source_db_name)
        source_collection = source_db[source_collection_name]
        
        # Required fields to read
        projection = {
            "Statute_Name": 1,
            "Sections": 1,
            "Province": 1,
            "Statute_Type": 1,
            "Year": 1,
            "Date": 1,
            "_id": 1,
            "legal_category": 1
        }
        
        statutes = []
        cursor = source_collection.find({}, projection)
        async for doc in cursor:
            # Convert all ObjectIds to strings for JSON serialization
            doc = convert_objectids_to_strings(doc)
            statutes.append(doc)
        
        logger.info(f"Fetched {len(statutes)} statutes from {source_db_name}.{source_collection_name}")
        return statutes

    def _normalize_province(self, province: str) -> str:
        """Normalize province name to standard form."""
        if not province:
            return "unknown"
        
        province_lower = province.lower().strip()
        mapping = {
            "federal": "federal",
            "punjab": "punjab", 
            "sindh": "sindh",
            "kpk": "kpk",
            "khyber pakhtunkhwa": "kpk",
            "balochistan": "balochistan",
            "baluchistan": "balochistan",
            "gilgit baltistan": "gb",
            "gb": "gb",
            "ajk": "ajk",
            "azad jammu kashmir": "ajk"
        }
        
        return mapping.get(province_lower, province_lower)

    def _extract_year(self, statute: Dict[str, Any]) -> Optional[str]:
        """Extract year from various date fields."""
        for field in ["Year", "Date", "Date_of_Commencement", "Date_of_Assent", "Date_Enacted"]:
            value = statute.get(field)
            if value:
                if isinstance(value, str) and len(value) >= 4:
                    year_match = re.search(r'\b(19|20)\d{2}\b', value)
                    if year_match:
                        return year_match.group(0)
                elif isinstance(value, datetime):
                    return str(value.year)
        return None

    def _extract_base_name(self, statute_name: str) -> str:
        """Extract base name from statute name, removing version patterns."""
        if not statute_name:
            return "unknown"
        
        base_name = statute_name.strip()
        
        # Remove common patterns
        patterns = [
            r'\s*\([^)]*amendment[^)]*\)\s*',     # (Amendment), (Second Amendment)
            r'\s*\([^)]*revised[^)]*\)\s*',       # (Revised)
            r'\s*amendment\s*(?:\d{4})?\s*$',     # Amendment 2020
            r'\s*\(no\.\s*\d+\)\s*',              # (No. 5)
            r'\s*no\.\s*\d+\s*$',                 # No. 12
            r'\s*,\s*\d{4}\s*$',                  # , 1997
            r'\s*\d{4}\s*$'                       # 1997
        ]
        
        for pattern in patterns:
            base_name = re.sub(pattern, '', base_name, flags=re.IGNORECASE)
        
        # Clean up extra whitespace and punctuation
        base_name = re.sub(r'\s+', ' ', base_name).strip()
        base_name = re.sub(r'[,\s]+$', '', base_name)
        
        return base_name if base_name else "unknown"

    def _make_slug(self, text: str) -> str:
        """Convert text to URL-safe slug."""
        if not text:
            return "unknown"
        
        # Normalize unicode
        text = unicodedata.normalize('NFKD', text)
        # Remove non-alphanumeric characters
        text = re.sub(r'[^\w\s-]', '', text)
        # Replace spaces and multiple hyphens with single hyphen
        text = re.sub(r'[\s_-]+', '_', text)
        # Convert to lowercase
        return text.lower().strip('_')

    def _build_statute_snippet(self, statute: Dict[str, Any], config: Phase5Config) -> str:
        """Build context snippet from preamble and early sections."""
        sections = statute.get("Sections", [])
        if not isinstance(sections, list):
            return statute.get("Statute_Name", "")
        
        snippet_parts = []
        char_count = 0
        sections_added = 0
        
        # Add preamble first if present
        for section in sections:
            if (isinstance(section, dict) and 
                section.get("number", "").upper() in ["PREAMBLE", "0"]):
                text = section.get("text", "").strip()
                if text:
                    preamble_text = text[:config.section_snippet_chars]
                    snippet_parts.append(f"PREAMBLE: {preamble_text}")
                    char_count += len(preamble_text) + 10
                    break
        
        # Add first N non-preamble sections
        for section in sections:
            if sections_added >= config.max_sections:
                break
            if char_count >= config.max_snippet_chars:
                break
                
            if (isinstance(section, dict) and 
                section.get("number", "").upper() not in ["PREAMBLE", "0"]):
                number = section.get("number", "")
                title = section.get("title", "")
                text = section.get("text", "").strip()
                
                if text:
                    section_text = text[:config.section_snippet_chars]
                    if title:
                        section_part = f"Section {number}: {title} - {section_text}"
                    else:
                        section_part = f"Section {number}: {section_text}"
                    
                    snippet_parts.append(section_part)
                    char_count += len(section_part)
                    sections_added += 1
        
        snippet = " | ".join(snippet_parts)
        if len(snippet) > config.max_snippet_chars:
            snippet = snippet[:config.max_snippet_chars - 3] + "..."
        
        return snippet if snippet else statute.get("Statute_Name", "")

    async def _call_gpt_grouping(self, batch: List[Dict[str, Any]], config: Phase5Config) -> GPTGroupingRequest:
        """Call GPT to group statutes and determine relations."""
        if not self.azure_openai_client or len(batch) < 2:
            # Fallback: each statute in its own group
            groups = [[i] for i in range(len(batch))]
            relations = {str(i): {"relation": "unknown", "confidence": 0.0} for i in range(len(batch))}
            similarity = {str(i): 1.0 for i in range(len(batch))}
            return GPTGroupingRequest(groups=groups, relations=relations, similarity=similarity)
        
        # Build input for GPT
        input_statutes = []
        for i, statute in enumerate(batch):
            snippet = self._build_statute_snippet(statute, config)
            year = self._extract_year(statute) or "unknown"
            
            input_statutes.append({
                "i": i,
                "title": statute.get("Statute_Name", ""),
                "province": self._normalize_province(statute.get("Province", "")),
                "type": statute.get("Statute_Type", ""),
                "year": year,
                "snippet": snippet
            })
        
        user_prompt = f"""Group the following statutes by semantic equivalence into arrays of index lists.
Also return per-index relation labels and confidence.

INPUT:
{json.dumps(input_statutes, indent=2)}

RESPONSE JSON SCHEMA:
{{
  "groups": [[0, 2, 5], [1], [3, 4]],
  "relations": {{
    "0": {{"relation": "original|amendment|ordinance|repeal|supplement|unknown", "confidence": 0.0..1.0}},
    "1": {{"relation": "...", "confidence": ...}}
  }},
  "similarity": {{
    "0": 0.0..1.0,
    "1": 0.0..1.0
  }}
}}

Return ONLY valid JSON that matches the schema."""
        
        # Call GPT with retries
        for attempt in range(config.retries):
            try:
                response = self.azure_openai_client.chat.completions.create(
                    model=self.deployment_name,
                    temperature=0.1,
                    max_tokens=1200,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    response_format={"type": "json_object"}
                )
                
                content = response.choices[0].message.content.strip()
                logger.debug(f"GPT response: {content}")
                
                # Parse and validate JSON
                parsed = json.loads(content)
                return GPTGroupingRequest(**parsed)
                
            except (json.JSONDecodeError, ValidationError) as e:
                logger.warning(f"GPT response parse error (attempt {attempt + 1}): {e}")
                if attempt == config.retries - 1:
                    break
            except Exception as e:
                logger.warning(f"GPT call failed (attempt {attempt + 1}): {e}")
                if attempt < config.retries - 1:
                    await asyncio.sleep(config.backoff_seconds * (attempt + 1))
                else:
                    break
        
        # Fallback to rule-based grouping
        logger.warning("GPT grouping failed, using fallback")
        return self._fallback_grouping(batch)

    def _fallback_grouping(self, batch: List[Dict[str, Any]]) -> GPTGroupingRequest:
        """Fallback rule-based grouping when GPT fails."""
        groups = []
        relations = {}
        similarity = {}
        processed = set()
        
        for i, statute_a in enumerate(batch):
            if i in processed:
                continue
                
            group = [i]
            base_name_a = self._extract_base_name(statute_a.get("Statute_Name", ""))
            province_a = self._normalize_province(statute_a.get("Province", ""))
            type_a = statute_a.get("Statute_Type", "")
            
            # Find similar statutes
            for j, statute_b in enumerate(batch[i+1:], i+1):
                if j in processed:
                    continue
                    
                base_name_b = self._extract_base_name(statute_b.get("Statute_Name", ""))
                province_b = self._normalize_province(statute_b.get("Province", ""))
                type_b = statute_b.get("Statute_Type", "")
                
                # Check if should group
                if (base_name_a == base_name_b and 
                    province_a == province_b and 
                    type_a == type_b):
                    group.append(j)
                    processed.add(j)
            
            if group:
                groups.append(group)
                processed.update(group)
                
                # Assign relations (basic heuristic)
                for idx in group:
                    relations[str(idx)] = {"relation": "unknown", "confidence": 0.5}
                    similarity[str(idx)] = 0.8 if len(group) > 1 else 1.0
        
        return GPTGroupingRequest(groups=groups, relations=relations, similarity=similarity)

    def _determine_original_statute(self, group_statutes: List[Dict[str, Any]]) -> int:
        """Determine which statute in the group is the original (oldest)."""
        if len(group_statutes) == 1:
            return 0
        
        # Sort by year, then by title analysis
        def sort_key(item):
            idx, statute = item
            year = self._extract_year(statute)
            year_int = int(year) if year and year.isdigit() else 9999
            
            # Prefer statutes without "amendment" in title
            title = statute.get("Statute_Name", "").lower()
            has_amendment = "amendment" in title
            
            return (year_int, has_amendment, idx)
        
        indexed_statutes = list(enumerate(group_statutes))
        sorted_statutes = sorted(indexed_statutes, key=sort_key)
        
        return sorted_statutes[0][0]

    def _convert_sections_to_models(self, sections: List[Dict[str, Any]]) -> List[StatuteSection]:
        """Convert raw sections to StatuteSection models."""
        if not isinstance(sections, list):
            return []
        
        section_models = []
        for section in sections:
            if isinstance(section, dict):
                section_models.append(StatuteSection(
                    number=str(section.get("number", "")),
                    title=section.get("title", ""),
                    text=section.get("text", ""),
                    citations=section.get("citations", []) if isinstance(section.get("citations"), list) else [],
                    bookmark_id=section.get("bookmark_id")
                ))
        
        return section_models

    async def _create_group_document(self, group_statutes: List[Dict[str, Any]], 
                                   group_relations: Dict[str, Dict[str, Any]], 
                                   group_similarity: Dict[str, float], 
                                   legal_category: Optional[int]) -> StatuteGroup:
        """Create a group document from grouped statutes."""
        if not group_statutes:
            raise ValueError("Cannot create group from empty statutes list")
        
        # Determine original statute
        original_idx = self._determine_original_statute(group_statutes)
        original_statute = group_statutes[original_idx]
        
        # Extract common properties
        base_name = self._extract_base_name(original_statute.get("Statute_Name", ""))
        province = self._normalize_province(original_statute.get("Province", ""))
        statute_type = original_statute.get("Statute_Type", "")
        
        # Create group ID
        group_id = f"group_{legal_category or 0}_{province}_{self._make_slug(base_name)}_{self._make_slug(statute_type)}"
        
        # Convert statutes to nested format
        nested_statutes = []
        amendment_count = 0
        
        for i, statute in enumerate(group_statutes):
            is_original = (i == original_idx)
            relation_data = group_relations.get(str(i), {"relation": "unknown", "confidence": 0.0})
            
            if is_original:
                relation = "original"
            else:
                relation = relation_data.get("relation", "unknown")
                if relation in ["amendment", "ordinance", "repeal", "supplement"]:
                    amendment_count += 1
            
            nested_statute = NestedStatute(
                _id=str(statute.get("_id", "")),
                title=statute.get("Statute_Name", ""),
                year=self._extract_year(statute),
                province=province,
                statute_type=statute_type,
                is_original=is_original,
                relation=relation,
                semantic_similarity_score=group_similarity.get(str(i)),
                ai_decision_confidence=relation_data.get("confidence"),
                sections=self._convert_sections_to_models(statute.get("Sections", []))
            )
            nested_statutes.append(nested_statute)
        
        # Create group document
        now_iso = datetime.now().isoformat()
        group_doc = StatuteGroup(
            group_id=group_id,
            base_name=base_name,
            province=province,
            statute_type=statute_type,
            legal_category=legal_category,
            total_statutes=len(nested_statutes),
            original_statute_id=str(original_statute.get("_id", "")),
            amendment_count=amendment_count,
            created_at=now_iso,
            updated_at=now_iso,
            statutes=nested_statutes
        )
        
        return group_doc

    async def _save_group_document(self, group_doc: StatuteGroup, config: Phase5Config):
        """Save group document to target collection."""
        target_db = self.client.get_database(config.target_database)
        target_collection = target_db[config.get_target_collection()]
        
        # Upsert by group_id
        group_dict = group_doc.dict()
        await target_collection.replace_one(
            {"group_id": group_doc.group_id},
            group_dict,
            upsert=True
        )

    async def _ensure_indexes(self, config: Phase5Config):
        """Ensure required indexes exist on target collection."""
        target_db = self.client.get_database(config.target_database)
        target_collection = target_db[config.get_target_collection()]
        
        indexes = [
            ("group_id", 1),
            ("province", 1),
            ("base_name", 1),
            ("statute_type", 1),
            ("legal_category", 1),
            ("updated_at", 1)
        ]
        
        for index_spec in indexes:
            try:
                await target_collection.create_index([index_spec])
            except Exception as e:
                logger.debug(f"Index creation skipped (likely exists): {e}")

    async def group_and_version_statutes(
        self, 
        config: Optional[Phase5Config] = None,
        progress_callback: Optional[callable] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Main method to group and version statutes with contextual analysis."""
        
        if config is None:
            config = self.default_config
        
        try:
            # Fetch source statutes
            yield {"status": "fetching", "message": "Fetching statutes from source collection", "progress": 0}
            
            statutes = await self._fetch_statutes(config)
            total_statutes = len(statutes)
            
            if total_statutes == 0:
                yield {"status": "completed", "message": "No statutes found in source collection", "progress": 100}
                return
            
            # Ensure target indexes
            await self._ensure_indexes(config)
            
            # Partition by province and statute_type
            partitions = defaultdict(list)
            for statute in statutes:
                province = self._normalize_province(statute.get("Province", ""))
                statute_type = statute.get("Statute_Type", "")
                key = (province, statute_type)
                partitions[key].append(statute)
            
            # Process each partition
            total_groups_created = 0
            processed_statutes = 0
            
            for partition_idx, ((province, statute_type), partition_statutes) in enumerate(partitions.items()):
                yield {
                    "status": "processing",
                    "message": f"Processing partition {partition_idx + 1}/{len(partitions)}: {province} {statute_type}",
                    "progress": int((processed_statutes / total_statutes) * 100),
                    "partition": f"{province}_{statute_type}",
                    "processed": processed_statutes,
                    "total": total_statutes,
                    "groups_created": total_groups_created
                }
                
                # Process partition in batches
                for batch_start in range(0, len(partition_statutes), config.batch_size):
                    batch_end = min(batch_start + config.batch_size, len(partition_statutes))
                    batch = partition_statutes[batch_start:batch_end]
                    
                    try:
                        # Call GPT for grouping
                        gpt_response = await self._call_gpt_grouping(batch, config)
                        
                        # Create groups from GPT response
                        for group_indices in gpt_response.groups:
                            if not group_indices:
                                continue
                                
                            group_statutes = [batch[i] for i in group_indices]
                            group_relations = {str(local_i): gpt_response.relations.get(str(batch_start + group_indices[local_i]), {"relation": "unknown", "confidence": 0.0}) 
                                             for local_i in range(len(group_indices))}
                            group_similarity = {str(local_i): gpt_response.similarity.get(str(batch_start + group_indices[local_i]), 0.0) 
                                              for local_i in range(len(group_indices))}
                            
                            # Get legal category from first statute
                            legal_category = group_statutes[0].get("legal_category")
                            
                            # Create and save group document
                            group_doc = await self._create_group_document(
                                group_statutes, group_relations, group_similarity, legal_category
                            )
                            await self._save_group_document(group_doc, config)
                            total_groups_created += 1
                            
                    except Exception as e:
                        logger.error(f"Error processing batch {batch_start}-{batch_end}: {e}")
                        logger.error(traceback.format_exc())
                    
                    processed_statutes += len(batch)
                    
                    # Yield progress
                    yield {
                        "status": "processing",
                        "message": f"Processed {len(batch)} statutes in {province} {statute_type}",
                        "progress": int((processed_statutes / total_statutes) * 100),
                        "processed": processed_statutes,
                        "total": total_statutes,
                        "groups_created": total_groups_created
                    }
            
            # Final status
            yield {
                "status": "completed",
                "message": f"Successfully created {total_groups_created} statute groups from {total_statutes} statutes",
                "progress": 100,
                "processed": total_statutes,
                "total": total_statutes,
                "groups_created": total_groups_created,
                "summary": {
                    "total_statutes_processed": total_statutes,
                    "total_groups_created": total_groups_created,
                    "partitions_processed": len(partitions),
                    "target_collection": f"{config.target_database}.{config.get_target_collection()}"
                }
            }
            
        except Exception as e:
            logger.error(f"Error in group_and_version_statutes: {e}")
            logger.error(traceback.format_exc())
            yield {
                "status": "error",
                "message": f"Processing failed: {str(e)}",
                "progress": 0,
                "error": str(e)
            }

    async def get_grouped_statutes(
        self,
        config: Optional[Phase5Config] = None,
        page: int = 1,
        page_size: int = 50,
        province: Optional[str] = None,
        statute_type: Optional[str] = None,
        base_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get paginated grouped statutes with filtering."""
        
        if config is None:
            config = self.default_config
        
        target_db = self.client.get_database(config.target_database)
        target_collection = target_db[config.get_target_collection()]
        
        # Build filter
        filter_query = {}
        if province:
            filter_query["province"] = province
        if statute_type:
            filter_query["statute_type"] = statute_type
        if base_name:
            filter_query["base_name"] = {"$regex": re.escape(base_name), "$options": "i"}
        
        # Get total count
        total = await target_collection.count_documents(filter_query)
        
        # Calculate pagination
        skip = (page - 1) * page_size
        pages = (total + page_size - 1) // page_size
        
        # Fetch documents
        cursor = target_collection.find(filter_query).skip(skip).limit(page_size).sort("updated_at", -1)
        items = []
        async for doc in cursor:
            # Convert all ObjectIds to strings for JSON serialization
            doc = convert_objectids_to_strings(doc)
            items.append(doc)
        
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": pages
        }

    def stop_processing(self):
        """Stop the current processing operation."""
        self._should_stop = True
        logger.info("Processing stop requested")

    async def get_processing_status(self) -> Dict[str, Any]:
        """Get current processing status."""
        return {
            "is_running": not self._should_stop,
            "progress": self._current_progress
        }

    async def get_status(self, collection: Optional[str] = None) -> Dict[str, Any]:
        """Get current service status for a specific collection or autodetected one."""
        try:
            # Use provided collection or autodetect
            if collection:
                # Try to find the collection in available databases
                source_db_name = None
                source_collection_name = collection
                
                # Check Date-Enriched-Batches first, then Batched-Statutes, then Statutes
                for db_name in ["Date-Enriched-Batches", "Batched-Statutes", "Statutes"]:
                    db = self.client.get_database(db_name)
                    collections = await db.list_collection_names()
                    if collection in collections:
                        source_db_name = db_name
                        break
                
                if not source_db_name:
                    # Fallback to autodetection if collection not found
                    source_db_name, source_collection_name = await self._autodetect_source_collection(self.default_config)
            else:
                # Autodetect source
                source_db_name, source_collection_name = await self._autodetect_source_collection(self.default_config)
            
            source_db = self.client.get_database(source_db_name)
            source_count = await source_db[source_collection_name].count_documents({})
            
            # Check target database
            target_db = self.client.get_database(self.default_config.target_database)
            target_collections = await target_db.list_collection_names()
            
            # Use collection-specific target name if collection was specified
            if collection:
                config_for_collection = Phase5Config(source_collection=collection)
                target_collection_name = config_for_collection.get_target_collection()
            else:
                target_collection_name = self.default_config.get_target_collection()
            
            grouped_count = 0
            if target_collection_name in target_collections:
                grouped_count = await target_db[target_collection_name].count_documents({})
            
            return {
                "source_database": source_db_name,
                "source_collection": source_collection_name,
                "target_database": self.default_config.target_database,
                "target_collection": target_collection_name,
                "total_source_documents": source_count,
                "grouped_documents": grouped_count,
                "azure_openai_configured": bool(self.azure_openai_client),
                "deployment_name": self.deployment_name or "gpt-4o",
                "current_progress": self._current_progress
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "total_source_documents": 0,
                "grouped_documents": 0,
                "azure_openai_configured": False,
                "deployment_name": "unknown",
                "current_progress": 0.0
            }

    async def get_available_collections(self) -> List[str]:
        """Get available collections from autodetected database."""
        try:
            source_db_name, _ = await self._autodetect_source_collection(self.default_config)
            source_db = self.client.get_database(source_db_name)
            all_collections = await source_db.list_collection_names()
            # Filter for batch collections
            batch_collections = [col for col in all_collections if col.startswith("batch")]
            return sorted(batch_collections)
        except Exception as e:
            logger.error(f"Failed to get available collections: {e}")
            return []

    async def get_provinces(self) -> List[str]:
        """Get unique provinces from source collections."""
        try:
            source_db_name, _ = await self._autodetect_source_collection(self.default_config)
            source_db = self.client.get_database(source_db_name)
            provinces = set()
            
            # Get all batch collections
            collections = await self.get_available_collections()
            
            for collection_name in collections:
                collection = source_db[collection_name]
                # Get distinct provinces from this collection
                distinct_provinces = await collection.distinct("Province")
                
                for province in distinct_provinces:
                    if province and isinstance(province, str) and province.strip():
                        provinces.add(province.strip())
            
            # Return sorted list, excluding None/empty values
            return sorted([p for p in provinces if p])
            
        except Exception as e:
            logger.error(f"Failed to get provinces: {e}")
            return []

    async def get_grouping_statistics(self, collection_name: str) -> Dict[str, Any]:
        """Get statistics for grouping analysis"""
        try:
            source_db_name, _ = await self._autodetect_source_collection(self.default_config)
            source_db = self.client.get_database(source_db_name)
            collection = source_db[collection_name]
            
            total_count = await collection.count_documents({})
            
            # Get province distribution
            province_pipeline = [
                {"$group": {"_id": "$Province", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}}
            ]
            province_dist = await collection.aggregate(province_pipeline).to_list(length=None)
            
            # Get statute type distribution
            type_pipeline = [
                {"$group": {"_id": "$Statute_Type", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}}
            ]
            type_dist = await collection.aggregate(type_pipeline).to_list(length=None)
            
            return {
                "total_statutes": total_count,
                "province_distribution": [{"province": item["_id"], "count": item["count"]} for item in province_dist],
                "type_distribution": [{"type": item["_id"], "count": item["count"]} for item in type_dist],
                "collection_name": collection_name,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting grouping statistics: {e}")
            return {
                "total_statutes": 0,
                "province_distribution": [],
                "type_distribution": [],
                "collection_name": collection_name,
                "error": str(e)
            }
