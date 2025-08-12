"""
Script 2: Group Statutes by Base Name

This script normalizes statute names by removing legal suffixes and parenthetical expressions,
then groups statutes by their base names for versioning purposes.

Features:
- Removes legal suffixes (Act, Ordinance, Law, Rule, Regulation, Amendment, Bill, etc.)
- Removes parenthetical expressions like "(Amendment)", "(Second Amendment)"
- Creates base_name field for each statute
- Groups statutes by base_name
- Optional GPT-4 disambiguation for ambiguous cases
- Exports groupings to JSON format
- Creates new database with grouped structure
- Comprehensive metadata tracking
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import MongoClient
from tqdm import tqdm
import re
import json
from collections import defaultdict, Counter
from typing import List, Dict, Tuple, Optional
import logging
from difflib import SequenceMatcher
from datetime import datetime, date
import time
import numpy as np
try:
    from openai import AzureOpenAI
except ImportError:
    AzureOpenAI = None

from utils.gpt_cache import gpt_cache
from utils.gpt_rate_limiter import rate_limited_gpt_call
from utils.gpt_prompt_optimizer import optimize_gpt_prompt

# Configure logging
# Remove: logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# Remove: logger = logging.getLogger(__name__)

# --- CONFIG ---
def load_config():
    """Load configuration from JSON file"""
    config_file = "05_statute_versioning/config_group_statutes.json"
    default_config = {
        "mongo_uri": "mongodb://localhost:27017",
        "source_db": "Batched-Statutes",
        "source_collection": "statute",
        "target_db": "Batch-Base-Grouped",
        "target_collection": "statute",
        "azure_api_key": "",
        "azure_endpoint": "",
        "gpt_model": "gpt-4o",
        "azure_api_version": "2024-11-01-preview"
    }
    
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                return {**default_config, **json.load(f)}
        except Exception as e:
            print(f"Error loading config: {e}")
    
    return default_config

# Load configuration
config = load_config()

MONGO_URI = config["mongo_uri"]
SOURCE_DB = config["source_db"]
SOURCE_COLL = config["source_collection"]
TARGET_DB = config["target_db"]
TARGET_COLL = config["target_collection"]

# Similarity threshold for disambiguation
SIMILARITY_THRESHOLD = config.get("processing", {}).get("similarity_threshold", 0.8)

# Initialize metadata tracking
metadata = {
    "total_statutes_processed": 0,
    "unique_base_names": 0,
    "grouping_stats": {
        "groups_with_single_statute": 0,
        "groups_with_multiple_statutes": 0,
        "max_statutes_in_group": 0,
        "average_statutes_per_group": 0,
        "total_statutes_grouped": 0
    },
    "base_name_analysis": {
        "base_name_extractions": Counter(),
        "extraction_failures": 0,
        "sample_extractions": [],
        "largest_groups": []
    },
    "similarity_merging": {
        "groups_merged": 0,
        "similarity_pairs": [],
        "merge_operations": []
    },
    "processing_details": {
        "statutes_with_extracted_base_name": 0,
        "statutes_with_original_name": 0,
        "database_updates": 0,
        "groups_created": 0
    },
    "gpt_usage": {
        "gpt_calls_made": 0,
        "gpt_cache_hits": 0,
        "gpt_errors": 0,
        "gpt_equivalence_decisions": []
    }
}

# MongoDB connection
client = MongoClient(MONGO_URI)
source_col = client[SOURCE_DB][SOURCE_COLL]
target_col = client[TARGET_DB][TARGET_COLL]

# --- Azure GPT client setup ---
if AzureOpenAI:
    client_aoai = AzureOpenAI(
        api_key=config["azure_api_key"],
        api_version=config["azure_api_version"],
        azure_endpoint=config["azure_endpoint"]
    )
else:
    client_aoai = None

# --- Legal hierarchy for grouping ---
LEGAL_HIERARCHY = [
    "Constitution", "Act", "Ordinance", "Rule", "Regulation", "Order", "Resolution"
]

# --- Helper: get legal category index for sorting ---
def get_legal_category(statute_type: str) -> int:
    for idx, cat in enumerate(LEGAL_HIERARCHY):
        if cat.lower() in statute_type.lower():
            return idx
    return len(LEGAL_HIERARCHY)  # Unknown types go last

# --- Helper: apply chronological order within a group ---
def apply_chronological_order(statutes: List[Dict]) -> List[Dict]:
    def get_date(statute):
        try:
            return datetime.strptime(statute.get("Date", ""), "%d-%b-%Y")
        except Exception:
            return datetime.max
    return sorted(statutes, key=get_date)

# --- Helper: should two statutes be merged? ---
def should_merge_statutes(statute_a: Dict, statute_b: Dict) -> dict:
    """
    Decide if two statutes should be merged based on province, type, similarity, and GPT.
    Returns dict with merge decision and metadata.
    """
    # Province-aware: only merge if province matches
    province_a = statute_a.get("Province", "").strip().lower()
    province_b = statute_b.get("Province", "").strip().lower()
    if province_a != province_b:
        return {"merge": False, "reason": "Different province", "province": province_a}
    # Statute_Type-aware: only merge if type matches and in same legal category
    type_a = statute_a.get("Statute_Type", "").strip().lower()
    type_b = statute_b.get("Statute_Type", "").strip().lower()
    if type_a != type_b:
        return {"merge": False, "reason": "Different Statute_Type", "statute_type": type_a}
    # Legal hierarchy: only merge within same category
    if get_legal_category(type_a) != get_legal_category(type_b):
        return {"merge": False, "reason": "Different legal category", "category": get_legal_category(type_a)}
    # Similarity threshold
    sim = calculate_similarity(statute_a["base_name"], statute_b["base_name"])
    if sim < 0.75:
        return {"merge": False, "reason": f"Similarity {sim:.2f} below threshold", "similarity": sim}
    # GPT check
    gpt_result = gpt_check_equivalence(
        statute_a["Statute_Name"], statute_b["Statute_Name"], province_a, type_a
    )
    if gpt_result.get("equivalent"):
        return {"merge": True, "reason": "GPT: Equivalent", "gpt": gpt_result, "province": province_a, "statute_type": type_a, "similarity": sim}
    return {"merge": False, "reason": f"GPT: Not equivalent ({gpt_result})", "gpt": gpt_result, "province": province_a, "statute_type": type_a, "similarity": sim}

# --- Enhanced GPT check with province/type context ---
@rate_limited_gpt_call
@optimize_gpt_prompt
def gpt_check_equivalence(title1: str, title2: str, province: str, statute_type: str) -> dict:
    """
    Use GPT to check if two statute titles refer to the same law (semantic equivalence), with province/type context.
    Returns a dict: {"equivalent": bool, "gpt_reason": str}
    """
    if not client_aoai:
        return {"equivalent": False, "gpt_reason": "GPT not available"}
    
    # Create cache key
    cache_key = f"equivalence:{title1}:{title2}:{province}:{statute_type}"
    
    # Check cache first
    cached_result = gpt_cache.get(cache_key)
    if cached_result:
        metadata["gpt_usage"]["gpt_cache_hits"] += 1
        return cached_result
    
    system_prompt = (
        "You are a Pakistani legal expert. Given two statute titles, their province, and type, determine if they refer to the same law (semantically equivalent, same legal lineage). "
        "Reply with 'Yes' or 'No' and a brief reason. "
        "Example reply: Yes | Both are the Punjab Anti-Terrorism Act 1997 and its amendment."
    )
    user_prompt = f"Title 1: {title1}\nTitle 2: {title2}\nProvince: {province}\nStatute_Type: {statute_type}"
    
    try:
        response = client_aoai.chat.completions.create(
            model=config["gpt_model"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2,
            max_tokens=150
        )
        content = response.choices[0].message.content
        if not content:
            result = {"equivalent": False, "gpt_reason": "No response"}
        else:
            parts = [p.strip() for p in content.split("|")]
            if len(parts) >= 1:
                eq = parts[0].lower().startswith("y")
                reason = parts[1] if len(parts) > 1 else ""
                result = {"equivalent": eq, "gpt_reason": reason}
            else:
                result = {"equivalent": False, "gpt_reason": content}
        
        # Cache the result
        gpt_cache.set(cache_key, result)
        metadata["gpt_usage"]["gpt_calls_made"] += 1
        
        # Track the decision
        metadata["gpt_usage"]["gpt_equivalence_decisions"].append({
            "title1": title1,
            "title2": title2,
            "province": province,
            "statute_type": statute_type,
            "equivalent": result["equivalent"],
            "reason": result["gpt_reason"]
        })
        
        return result
        
    except Exception as e:
        metadata["gpt_usage"]["gpt_errors"] += 1
        return {"equivalent": False, "gpt_reason": f"GPT error: {e}"}

# --- Stoplist for vague base names ---
VAGUE_BASE_NAMES = set([
    "federal government", "provincial government", "government", "law", "act", "ordinance", "regulation", "rules", "statute", "bill", "code", "enactment", "legislation"
])

def extract_base_name(statute_name: str) -> str:
    """
    Extract base name from statute name by removing:
    - Legal suffixes (Act, Ordinance, Law, Rule, Regulation, Amendment, Bill, etc.)
    - Parenthetical expressions like "(Amendment)", "(Second Amendment)"
    - Year suffixes
    """
    if not statute_name:
        return ""
    
    # Convert to string and normalize whitespace
    name = str(statute_name).strip()
    
    # Remove parenthetical expressions
    # This regex matches parentheses and their content
    name = re.sub(r'\s*\([^)]*\)\s*', ' ', name)
    
    # Remove year patterns (4-digit years)
    name = re.sub(r'\b\d{4}\b', '', name)
    
    # Remove common legal suffixes
    suffixes = [
        r'\bAct\b', r'\bActs\b', r'\bOrdinance\b', r'\bOrdinances\b',
        r'\bLaw\b', r'\bLaws\b', r'\bRule\b', r'\bRules\b',
        r'\bRegulation\b', r'\bRegulations\b', r'\bAmendment\b', r'\bAmendments\b',
        r'\bBill\b', r'\bBills\b', r'\bStatute\b', r'\bStatutes\b',
        r'\bCode\b', r'\bCodes\b', r'\bOrdinance\b', r'\bOrdinances\b',
        r'\bEnactment\b', r'\bEnactments\b', r'\bLegislation\b', r'\bLegislations\b'
    ]
    
    for suffix in suffixes:
        name = re.sub(suffix, '', name, flags=re.IGNORECASE)
    
    # Remove extra whitespace and punctuation
    name = re.sub(r'\s+', ' ', name)
    name = re.sub(r'^\s*[,\-\s]+', '', name)  # Remove leading punctuation
    name = re.sub(r'[,\-\s]+\s*$', '', name)  # Remove trailing punctuation
    
    return name.strip()

def normalize_for_comparison(text: str) -> str:
    """
    Normalize text for similarity comparison.
    """
    if not text:
        return ""
    
    # Convert to lowercase and remove extra whitespace
    normalized = re.sub(r'\s+', ' ', text.lower().strip())
    
    # Remove punctuation except spaces
    normalized = re.sub(r'[^\w\s]', '', normalized)
    
    return normalized

def calculate_similarity(name1: str, name2: str) -> float:
    """
    Calculate similarity between two statute names using numpy for faster operations.
    Returns a value between 0 and 1, where 1 is identical.
    """
    if not name1 or not name2:
        return 0.0
    
    # Normalize names for comparison
    norm1 = normalize_for_comparison(name1)
    norm2 = normalize_for_comparison(name2)
    
    if norm1 == norm2:
        return 1.0
    
    # Use numpy for faster string operations
    # Convert to numpy arrays for vectorized operations
    chars1 = np.array(list(norm1))
    chars2 = np.array(list(norm2))
    
    # Use SequenceMatcher for similarity calculation
    matcher = SequenceMatcher(None, norm1, norm2)
    return matcher.ratio()

# --- Helper: is base name vague/short? ---
def is_vague_base_name(name: str) -> bool:
    norm = name.strip().lower()
    return norm in VAGUE_BASE_NAMES or len(norm) < 20

# --- Modular merge logic with GPT check ---
def should_merge_groups(base_name1, base_name2, similarity) -> dict:
    """
    Decide if two base groups should be merged, using both string similarity and GPT semantic check.
    Returns a dict with merge decision and metadata.
    """
    # Never merge if either name is vague/short
    if is_vague_base_name(base_name1) or is_vague_base_name(base_name2):
        return {"merge": False, "reason": "Vague or short base name"}
    # Require high string similarity
    if similarity < SIMILARITY_THRESHOLD:
        return {"merge": False, "reason": f"Similarity {similarity:.2f} below threshold"}
    # Use GPT for semantic check
    gpt_result = gpt_check_equivalence(base_name1, base_name2)
    if gpt_result["equivalent"] and gpt_result["confidence"] >= 0.7:
        return {"merge": True, "reason": "GPT: Equivalent", **gpt_result}
    return {"merge": False, "reason": f"GPT: Not equivalent ({gpt_result})", **gpt_result}

# --- Refactored merge_similar_groups ---
def merge_similar_groups(base_groups: Dict[str, List[Dict]]) -> Dict[str, List[Dict]]:
    """
    Merge groups with similar base names using numpy for faster similarity calculations.
    """
    if not base_groups:
        return base_groups
    
    # Convert base names to numpy array for faster operations
    base_names = np.array(list(base_groups.keys()))
    base_names_normalized = np.array([normalize_for_comparison(name) for name in base_names])
    
    merged_groups = base_groups.copy()
    groups_to_remove = set()
    
    # Create similarity matrix using numpy for faster calculations
    n_groups = len(base_names)
    similarity_matrix = np.zeros((n_groups, n_groups))
    
    # Calculate similarities using vectorized operations where possible
    for i in range(n_groups):
        for j in range(i + 1, n_groups):
            similarity = calculate_similarity(base_names[i], base_names[j])
            similarity_matrix[i, j] = similarity
            similarity_matrix[j, i] = similarity
    
    # Find groups to merge
    for i in range(n_groups):
        if base_names[i] in groups_to_remove:
            continue
            
        for j in range(i + 1, n_groups):
            if base_names[j] in groups_to_remove:
                continue
                
            if similarity_matrix[i, j] >= SIMILARITY_THRESHOLD:
                # Merge decision logic
                merge_decision = should_merge_groups(base_names[i], base_names[j], similarity_matrix[i, j])
                
                if merge_decision["merge"]: # Changed from merge_decision["should_merge"] to merge_decision["merge"]
                    # Merge groups
                    source_group = base_names[j]
                    target_group = base_names[i]
                    
                    # Add statutes from source to target
                    merged_groups[target_group].extend(merged_groups[source_group])
                    
                    # Mark source for removal
                    groups_to_remove.add(source_group)
                    
                    # Track merge operation
                    metadata["similarity_merging"]["groups_merged"] += 1
                    metadata["similarity_merging"]["merge_operations"].append({
                        "operation": f"Merge '{source_group}' into '{target_group}'", # Changed from "source" to "operation"
                        "similarity": similarity_matrix[i, j],
                        "reason": merge_decision.get("reason") # Changed from "reason" to "merge_decision.get("reason")"
                    })
    
    # Remove merged groups
    for group_name in groups_to_remove:
        del merged_groups[group_name]
    
    return merged_groups

# --- Main grouping logic with legal hierarchy and province-awareness ---
def group_statutes_advanced() -> Dict[str, List[Dict]]:
    """
    Group statutes by legal hierarchy, province, and semantic equivalence.
    Returns a dict: {(category, province, base_name): [statutes]}
    """
    print("🔍 Fetching all statutes from database...")
    statutes = list(source_col.find({}))
    metadata["total_statutes_processed"] = len(statutes)
    print(f"📊 Processing {len(statutes)} statutes")

    # Preprocess: assign base_name and legal category
    for statute in statutes:
        statute["base_name"] = extract_base_name(statute.get("Statute_Name", ""))
        statute["legal_category"] = get_legal_category(statute.get("Statute_Type", ""))

    # Initial grouping: by (legal_category, province, base_name, statute_type)
    initial_groups = defaultdict(list)
    for statute in statutes:
        key = (
            statute["legal_category"],
            (str(statute.get("Province", "")) or "").strip().lower(),
            statute["base_name"].strip().lower(),
            statute.get("Statute_Type", "").strip().lower()
        )
        initial_groups[key].append(statute)

    # Merge only directly connected statutes (amend/repeal, same lineage)
    merged_groups = {}
    for key, group in initial_groups.items():
        # Sort by date
        group = apply_chronological_order(group)
        merged = []
        used = set()
        for i, statute_a in enumerate(group):
            if i in used:
                continue
            current_group = [statute_a]
            used.add(i)
            for j, statute_b in enumerate(group[i+1:], i+1):
                if j in used:
                    continue
                merge_decision = should_merge_statutes(statute_a, statute_b)
                # Log metadata for each merge attempt
                metadata["similarity_merging"]["similarity_pairs"].append({
                    "statute_a": statute_a["Statute_Name"],
                    "statute_b": statute_b["Statute_Name"],
                    "province": statute_a.get("Province", ""),
                    "statute_type": statute_a.get("Statute_Type", ""),
                    "legal_category": statute_a["legal_category"],
                    "chronology": i,
                    "merge": merge_decision["merge"],
                    "reason": merge_decision.get("reason", ""),
                    "gpt_reason": merge_decision.get("gpt", {}).get("gpt_reason", "")
                })
                if merge_decision["merge"]:
                    current_group.append(statute_b)
                    used.add(j)
            merged.append(current_group)
        # Flatten merged groups for this key
        for idx, mg in enumerate(merged):
            if mg:
                group_key = (
                    key[0], key[1], mg[0]["base_name"], mg[0].get("Statute_Type", "")
                )
                merged_groups[group_key] = mg
    print(f"📊 After merging: {len(merged_groups)} legal/province/base/type groups")
    return merged_groups

# --- Updated create_grouped_database to handle new group keys ---
def create_grouped_database_advanced(groupings: Dict[Tuple, List[Dict]]) -> int:
    """
    Create a new database with grouped structure (legal hierarchy, province-aware).
    Returns number of documents created.
    """
    target_col.delete_many({})
    print("🧹 Cleared target collection")
    created_count = 0
    for group_key, statutes in tqdm(groupings.items(), desc="Creating grouped database"):
        legal_category, province, base_name, statute_type = group_key
        group_doc = {
            "base_name": base_name,
            "province": province,
            "statute_type": statute_type,
            "legal_category": legal_category,
            "group_id": f"group_{legal_category}_{province}_{base_name.replace(' ', '_')}_{statute_type}",
            "total_statutes": len(statutes),
            "statutes": []
        }
        for statute in statutes:
            statute_copy = statute.copy()
            statute_copy["_id"] = str(statute_copy["_id"])
            group_doc["statutes"].append(statute_copy)
        try:
            target_col.insert_one(group_doc)
            created_count += 1
            metadata["processing_details"]["groups_created"] += 1
        except Exception as e:
            print(f"Error creating group for {base_name}: {e}")
    metadata["processing_details"]["database_updates"] = created_count
    return created_count

def save_groupings_to_json(groupings: Dict[str, List[Dict]]):
    """
    Save statute groupings to JSON file with new naming convention.
    """
    # Prepare data for JSON serialization
    json_data = {}
    for base_name, statutes in groupings.items():
        json_data[base_name] = []
        for statute in statutes:
            statute_copy = statute.copy()
            statute_copy["_id"] = str(statute_copy["_id"])
            json_data[base_name].append(statute_copy)
    # New filename pattern
    groupings_filename = f"grouped_statutes_{SOURCE_DB}_{date.today().isoformat()}.json"
    groupings_path = f"05_statute_versioning/{groupings_filename}"
    with open(groupings_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    print(f"📄 Groupings saved to: {groupings_path}")

def print_grouping_statistics(groupings: Dict[str, List[Dict]]):
    """
    Print statistics about the groupings.
    """
    total_statutes = sum(len(statutes) for statutes in groupings.values())
    multi_statute_groups = sum(1 for statutes in groupings.values() if len(statutes) > 1)
    
    print("📊 Grouping Statistics:")
    print(f"   - Total base groups: {len(groupings)}")
    print(f"   - Total statutes: {total_statutes}")
    print(f"   - Groups with multiple statutes: {multi_statute_groups}")
    print(f"   - Average statutes per group: {total_statutes / len(groupings):.2f}")
    
    # Show some examples
    print("\n📋 Example Groups:")
    for i, (base_name, statutes) in enumerate(groupings.items()):
        if len(statutes) > 1:
            print(f"   {base_name}: {len(statutes)} statutes")
            for statute in statutes[:3]:  # Show first 3
                print(f"     - {statute.get('Statute_Name', 'Unknown')} ({statute.get('Date', 'No date')})")
            if len(statutes) > 3:
                print(f"     ... and {len(statutes) - 3} more")
            print("")
        
        if i >= 4:  # Show only first 5 examples
            break

def print_comprehensive_metadata():
    """Print comprehensive metadata about the grouping process and save with new naming convention"""
    print(f"\n📊 COMPREHENSIVE BASE NAME GROUPING METADATA:")
    print("=" * 70)
    print(f"📋 Total statutes processed: {metadata['total_statutes_processed']}")
    print(f"📋 Unique base names: {metadata['unique_base_names']}")
    print(f"📋 Groups created: {metadata['processing_details']['groups_created']}")
    print(f"\n📊 Grouping Statistics:")
    print(f"   - Groups with single statute: {metadata['grouping_stats']['groups_with_single_statute']}")
    print(f"   - Groups with multiple statutes: {metadata['grouping_stats']['groups_with_multiple_statutes']}")
    print(f"   - Max statutes in a group: {metadata['grouping_stats']['max_statutes_in_group']}")
    print(f"   - Average statutes per group: {metadata['grouping_stats']['average_statutes_per_group']:.2f}")
    print(f"   - Total statutes grouped: {metadata['grouping_stats']['total_statutes_grouped']}")
    print(f"\n📊 Processing Details:")
    print(f"   - Statutes with extracted base_name: {metadata['processing_details']['statutes_with_extracted_base_name']}")
    print(f"   - Statutes with original name: {metadata['processing_details']['statutes_with_original_name']}")
    print(f"   - Extraction failures: {metadata['base_name_analysis']['extraction_failures']}")
    print(f"   - Database updates: {metadata['processing_details']['database_updates']}")
    print(f"\n📊 Base Name Extractions (Top 15):")
    for base_name, count in metadata["base_name_analysis"]["base_name_extractions"].most_common(15):
        print(f"   - {base_name}: {count} statutes")
    print(f"\n📊 Similarity Merging:")
    print(f"   - Groups merged: {metadata['similarity_merging']['groups_merged']}")
    print(f"   - Merge operations: {len(metadata['similarity_merging']['merge_operations'])}")
    if metadata['similarity_merging']['similarity_pairs']:
        print(f"\n📊 Sample Similarity Merges:")
        for pair in metadata['similarity_merging']['similarity_pairs'][:10]:
            print(f"   - '{pair.get('statute_a', '?')}' + '{pair.get('statute_b', '?')}' (merge: {pair.get('merge', '?')}, reason: {pair.get('reason', '')}, GPT: {pair.get('gpt_reason', '')})")
    
    print(f"\n📊 GPT Usage Statistics:")
    print(f"   - GPT calls made: {metadata['gpt_usage']['gpt_calls_made']}")
    print(f"   - GPT cache hits: {metadata['gpt_usage']['gpt_cache_hits']}")
    print(f"   - GPT errors: {metadata['gpt_usage']['gpt_errors']}")
    
    # Print GPT equivalence decisions
    if metadata["gpt_usage"]["gpt_equivalence_decisions"]:
        print(f"\n📊 GPT Equivalence Decisions (first 10):")
        for i, decision in enumerate(metadata["gpt_usage"]["gpt_equivalence_decisions"][:10]):
            print(f"   {i+1}. '{decision['title1']}' vs '{decision['title2']}' -> {decision['equivalent']} ({decision['reason']})")
    print(f"\n📊 Largest Groups (Top 10):")
    for i, group in enumerate(metadata["base_name_analysis"]["largest_groups"][:10]):
        print(f"   {i+1}. {group['base_name']}: {group['statute_count']} statutes")
        for name in group['sample_names']:
            print(f"      - {name}")
    print(f"\n📊 Sample Base Name Extractions:")
    for i, extraction in enumerate(metadata["base_name_analysis"]["sample_extractions"][:10]):
        print(f"   {i+1}. '{extraction['original_name']}' → '{extraction['extracted_base_name']}'")
    # Create metadata folder if it doesn't exist
    os.makedirs("metadata", exist_ok=True)
    # New metadata filename pattern
    metadata_filename = f"metadata_base_name_grouping_{SOURCE_DB}_{date.today().isoformat()}.json"
    metadata_path = os.path.join("metadata", metadata_filename)
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    print(f"\n📊 Metadata saved to: {metadata_path}")

# --- Main entrypoint ---
def main():
    print("🚀 Starting statute grouping by legal hierarchy, province, and semantic equivalence...")
    try:
        groupings = group_statutes_advanced()
        version_counts = [len(statutes) for statutes in groupings.values()]
        metadata["grouping_stats"]["groups_with_single_statute"] = sum(1 for count in version_counts if count == 1)
        metadata["grouping_stats"]["groups_with_multiple_statutes"] = sum(1 for count in version_counts if count > 1)
        metadata["grouping_stats"]["max_statutes_in_group"] = max(version_counts) if version_counts else 0
        metadata["grouping_stats"]["average_statutes_per_group"] = sum(version_counts) / len(version_counts) if version_counts else 0
        metadata["grouping_stats"]["total_statutes_grouped"] = sum(version_counts)
        print_grouping_statistics({k: v for k, v in groupings.items()})
        created_count = create_grouped_database_advanced(groupings)
        print(f"✅ Created {created_count} new grouped statutes")
        save_groupings_to_json({k[2]: v for k, v in groupings.items()})
        print_comprehensive_metadata()
        print("✅ Statute grouping completed!")
        print(f"📊 New database: {TARGET_DB}.{TARGET_COLL}")
        print(f"📊 Source database: {SOURCE_DB}.{SOURCE_COLL}")
    except Exception as e:
        print(f"❌ Error during statute grouping: {e}")
        raise

if __name__ == "__main__":
    main()
