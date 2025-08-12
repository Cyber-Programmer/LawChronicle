"""
Script 3: Assign Statute Versions

This script assigns version labels to statutes within each base group.
It sorts statutes chronologically and assigns labels like "Original", 
"First Amendment", "Second Amendment", etc.

Features:
- Sorts statutes by Date field chronologically
- Assigns version labels based on chronological order
- Handles missing or invalid dates
- Updates database with Version_Label field
- Exports versioning information to JSON
- Provides detailed statistics and examples
- Compatible with GPT-based semantic grouping (see group_statutes_by_base.py)
- Uses NumPy for performance optimization
- Integrates with Azure OpenAI GPT for complex ordering decisions
"""

import numpy as np
import pandas as pd
from pymongo import MongoClient
from tqdm import tqdm
import json
from datetime import datetime, date
from dateutil import parser
from collections import defaultdict, Counter
from typing import List, Dict, Tuple, Optional  
import os
import sys
import time
import re

# Add project root to Python path for utils imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.gpt_cache import gpt_cache
from utils.gpt_fallbacks import smart_statute_ordering, should_use_gpt_fallback
from utils.gpt_rate_limiter import rate_limited_gpt_call
from utils.gpt_prompt_optimizer import optimize_gpt_prompt

# Azure OpenAI imports
try:
    from openai import AzureOpenAI
except ImportError:
    AzureOpenAI = None

# --- CONFIG ---
def load_config():
    """Load configuration from JSON file"""
    config_file = "05_statute_versioning/config_assign_versions.json"
    default_config = {
        "mongo_uri": "mongodb://localhost:27017",
        "source_db": "Batch-Base-Grouped-Filled",
        "source_collection": "batch1",
        "target_db": "Batch-Statute-Versioned-Filled",
        "target_collection": "batch1",
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

# Initialize Azure OpenAI client
if AzureOpenAI:
    client_aoai = AzureOpenAI(
        api_key=config["azure_api_key"],
        api_version=config["azure_api_version"],
        azure_endpoint=config["azure_endpoint"]
    )
else:
    client_aoai = None

# Initialize metadata tracking
metadata = {
    "total_groups_processed": 0,
    "total_statutes_versioned": 0,
    "versioning_stats": {
        "groups_with_single_version": 0,
        "groups_with_multiple_versions": 0,
        "max_versions_in_group": 0,
        "average_versions_per_group": 0,
        "total_versions_created": 0
    },
    "version_label_distribution": {
        "version_labels": Counter(),
        "date_analysis": defaultdict(list),
        "sample_versions": []
    },
    "processing_details": {
        "statutes_with_valid_dates": 0,
        "statutes_with_invalid_dates": 0,
        "statutes_with_missing_dates": 0,
        "date_parsing_errors": 0,
        "groups_created": 0,
        "database_updates": 0
    },
    "gpt_usage": {
        "gpt_calls_made": 0,
        "gpt_cache_hits": 0,
        "gpt_errors": 0,
        "gpt_ordering_decisions": []
    }
}

# MongoDB connection
client = MongoClient(MONGO_URI)
source_db = client[SOURCE_DB]
source_col = source_db[SOURCE_COLL]
target_col = client[TARGET_DB][TARGET_COLL]

def parse_date_vectorized(date_strings: np.ndarray) -> np.ndarray:
    """
    Parse date strings using NumPy vectorized operations for better performance.
    Returns numpy array of datetime objects or None values.
    """
    if not date_strings.size:
        return np.array([])
    
    def parse_single_date(date_str):
        if not date_str or pd.isna(date_str):
            return None
        try:
            return parser.parse(str(date_str), fuzzy=True)
        except (ValueError, TypeError):
            return None
    
    # Vectorized parsing
    parsed_dates = np.vectorize(parse_single_date, otypes=[object])(date_strings)
    return parsed_dates

def get_version_label_vectorized(indices: np.ndarray, total_counts: np.ndarray) -> np.ndarray:
    """
    Generate version labels using NumPy vectorized operations.
    """
    def get_single_label(index, total):
        if index == 0:
            return "Original"
        elif index == 1:
            return "First Amendment"
        elif index == 2:
            return "Second Amendment"
        elif index == 3:
            return "Third Amendment"
        elif index == 4:
            return "Fourth Amendment"
        elif index == 5:
            return "Fifth Amendment"
        else:
            return f"{index + 1}th Amendment"
    
    return np.vectorize(get_single_label)(indices, total_counts)

def sort_statutes_by_date_vectorized(statutes: List[Dict]) -> List[Dict]:
    """
    Sort statutes by date chronologically using NumPy for better performance.
    Statutes without valid dates are placed at the end.
    """
    if not statutes:
        return []
    
    # Extract dates and convert to numpy array
    date_strings = np.array([statute.get("Date", "") for statute in statutes])
    parsed_dates = parse_date_vectorized(date_strings)
    
    # Create sort keys (use max datetime for invalid dates)
    sort_keys = np.where(parsed_dates != None, parsed_dates, np.datetime64('9999-12-31'))
    
    # Get sorted indices
    sorted_indices = np.argsort(sort_keys)
    
    # Return sorted statutes
    return [statutes[i] for i in sorted_indices]

@rate_limited_gpt_call
@optimize_gpt_prompt
def ask_gpt_for_version_order(statute_a: Dict, statute_b: Dict, group_name: str = "") -> Dict:
    """
    Use GPT to decide which statute came first if dates are identical or missing.
    Returns dict with 'order' ('A' or 'B') and 'reason'.
    """
    if not client_aoai:
        return {'order': 'A', 'reason': 'GPT not available'}
    
    # Create cache key
    cache_key = f"version_order:{statute_a.get('_id')}:{statute_b.get('_id')}"
    
    # Check cache first
    cached_result = gpt_cache.get(cache_key)
    if cached_result:
        metadata["gpt_usage"]["gpt_cache_hits"] += 1
        return cached_result
    
    try:
        # Prepare prompt
        system_prompt = """You are a legal expert analyzing Pakistani statutes. Given two statutes with identical or missing dates, determine which one came first based on:
1. Legal hierarchy (Act > Ordinance > Law > Rule > Regulation)
2. Amendment sequence (Original > First Amendment > Second Amendment)
3. Content analysis and context clues
4. Legal terminology and language evolution

Respond with 'A' or 'B' and a brief reason."""
        
        user_prompt = f"""
Group: {group_name}

Statute A: {statute_a.get('Statute_Name', '')}
- Date: {statute_a.get('Date', 'No date')}
- Type: {statute_a.get('Statute_Type', 'Unknown')}
- Province: {statute_a.get('Province', 'Unknown')}

Statute B: {statute_b.get('Statute_Name', '')}
- Date: {statute_b.get('Date', 'No date')}
- Type: {statute_b.get('Statute_Type', 'Unknown')}
- Province: {statute_b.get('Province', 'Unknown')}

Which statute came first? Respond with 'A' or 'B' and explain why.
"""
        
        response = client_aoai.chat.completions.create(
            model=config["gpt_model"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2,
            max_tokens=200
        )
        
        content = response.choices[0].message.content.strip()
        
        # Parse response
        if content.upper().startswith('A'):
            result = {'order': 'A', 'reason': content}
        elif content.upper().startswith('B'):
            result = {'order': 'B', 'reason': content}
        else:
            result = {'order': 'A', 'reason': f'GPT response unclear: {content}'}
        
        # Cache the result
        gpt_cache.set(cache_key, result)
        metadata["gpt_usage"]["gpt_calls_made"] += 1
        
        return result
        
    except Exception as e:
        metadata["gpt_usage"]["gpt_errors"] += 1
        return {'order': 'A', 'reason': f'GPT error: {str(e)}'}

def resolve_ambiguous_ordering_vectorized(statutes: List[Dict], group_name: str = "") -> List[Dict]:
    """
    Resolve ambiguous ordering using GPT when dates are identical or missing.
    Uses NumPy for efficient processing.
    """
    if len(statutes) < 2:
        return statutes
    
    # Convert to numpy arrays for efficient processing
    statute_array = np.array(statutes)
    date_strings = np.array([s.get("Date", "") for s in statutes])
    parsed_dates = parse_date_vectorized(date_strings)
    
    # Find pairs with identical or missing dates
    ambiguous_pairs = []
    for i in range(len(statutes) - 1):
        date1 = parsed_dates[i]
        date2 = parsed_dates[i + 1]
        
        if (date1 == date2) or (date1 is None and date2 is None):
            ambiguous_pairs.append((i, i + 1))
    
    # Resolve ambiguous pairs using GPT
    for i, j in ambiguous_pairs:
        if i < len(statute_array) and j < len(statute_array):
            gpt_result = ask_gpt_for_version_order(
                statute_array[i], 
                statute_array[j], 
                group_name
            )
            
            metadata["gpt_usage"]["gpt_ordering_decisions"].append({
                'group': group_name,
                'statute_a': statute_array[i].get('Statute_Name', ''),
                'statute_b': statute_array[j].get('Statute_Name', ''),
                'gpt_order': gpt_result['order'],
                'gpt_reason': gpt_result['reason']
            })
            
            # Swap if GPT says B should come first
            if gpt_result['order'] == 'B':
                statute_array[i], statute_array[j] = statute_array[j], statute_array[i]
                parsed_dates[i], parsed_dates[j] = parsed_dates[j], parsed_dates[i]
    
    return statute_array.tolist()

def assign_version_labels_vectorized(groupings: Dict[str, List[Dict]]) -> Dict[str, List[Dict]]:
    """
    Assign version labels to statutes within each base group using NumPy optimization.
    Returns updated groupings with version labels.
    """
    versioned_groupings = {}
    metadata["total_groups_processed"] = len(groupings)
    
    # Convert groupings to numpy arrays for batch processing
    base_names = np.array(list(groupings.keys()))
    statute_counts = np.array([len(statutes) for statutes in groupings.values()])
    
    for base_name, statutes in tqdm(groupings.items(), desc="Assigning version labels"):
        if not statutes:
            continue
            
        metadata["total_statutes_versioned"] += len(statutes)
        
        if len(statutes) == 1:
            # Single statute gets "Original" label
            statutes[0]["Version_Label"] = "Original"
            versioned_groupings[base_name] = statutes
            metadata["versioning_stats"]["groups_with_single_version"] += 1
            metadata["version_label_distribution"]["version_labels"]["Original"] += 1
            
            # Track date analysis
            date_str = statutes[0].get("Date", "")
            if date_str:
                try:
                    parsed_date = parser.parse(date_str, fuzzy=True)
                    if parsed_date:
                        metadata["version_label_distribution"]["date_analysis"][base_name].append(parsed_date.year)
                        metadata["processing_details"]["statutes_with_valid_dates"] += 1
                    else:
                        metadata["processing_details"]["statutes_with_invalid_dates"] += 1
                except:
                    metadata["processing_details"]["date_parsing_errors"] += 1
            else:
                metadata["processing_details"]["statutes_with_missing_dates"] += 1
        else:
            # Sort by date and resolve ambiguous ordering
            sorted_statutes = sort_statutes_by_date_vectorized(statutes)
            sorted_statutes = resolve_ambiguous_ordering_vectorized(sorted_statutes, base_name)
            
            # Assign version labels using vectorized operations
            indices = np.arange(len(sorted_statutes))
            total_count = np.full(len(sorted_statutes), len(sorted_statutes))
            version_labels = get_version_label_vectorized(indices, total_count)
            
            for i, (statute, label) in enumerate(zip(sorted_statutes, version_labels)):
                statute["Version_Label"] = label
                metadata["version_label_distribution"]["version_labels"][label] += 1
                
                # Track date analysis
                date_str = statute.get("Date", "")
                if date_str:
                    try:
                        parsed_date = parser.parse(date_str, fuzzy=True)
                        if parsed_date:
                            metadata["version_label_distribution"]["date_analysis"][base_name].append(parsed_date.year)
                            metadata["processing_details"]["statutes_with_valid_dates"] += 1
                        else:
                            metadata["processing_details"]["statutes_with_invalid_dates"] += 1
                    except:
                        metadata["processing_details"]["date_parsing_errors"] += 1
                else:
                    metadata["processing_details"]["statutes_with_missing_dates"] += 1
            
            versioned_groupings[base_name] = sorted_statutes
            metadata["versioning_stats"]["groups_with_multiple_versions"] += 1
            
            # Store sample versions
            if len(metadata["version_label_distribution"]["sample_versions"]) < 20:
                sample_group = {
                    "base_name": base_name,
                    "version_count": len(sorted_statutes),
                    "versions": []
                }
                for statute in sorted_statutes[:5]:  # Store first 5 versions
                    sample_group["versions"].append({
                        "version_label": statute.get("Version_Label", ""),
                        "statute_name": statute.get("Statute_Name", ""),
                        "date": statute.get("Date", ""),
                        "statute_id": str(statute.get("_id", ""))
                    })
                metadata["version_label_distribution"]["sample_versions"].append(sample_group)
    
    # Calculate final statistics using NumPy
    version_counts = np.array([len(statutes) for statutes in versioned_groupings.values()])
    if version_counts.size > 0:
        metadata["versioning_stats"]["max_versions_in_group"] = int(np.max(version_counts))
        metadata["versioning_stats"]["average_versions_per_group"] = float(np.mean(version_counts))
        metadata["versioning_stats"]["total_versions_created"] = int(np.sum(version_counts))
    
    return versioned_groupings

def update_database_with_versions_vectorized(statutes: List[Dict]) -> int:
    """
    Update the database with Version_Label field for all statutes using NumPy optimization.
    Returns number of updated documents.
    """
    if not statutes:
        return 0
    
    # Convert to numpy array for batch processing
    statute_array = np.array(statutes)
    updated_count = 0
    
    for statute in tqdm(statute_array, desc="Updating database with version labels"):
        try:
            result = target_col.update_one(
                {"_id": statute["_id"]},
                {"$set": {"Version_Label": statute["Version_Label"]}}
            )
            if result.modified_count > 0:
                updated_count += 1
        except Exception as e:
            print(f"Error updating statute {statute.get('_id')}: {e}")
    
    return updated_count

def create_versioned_database_vectorized(versioned_groupings: Dict[str, List[Dict]]) -> int:
    """
    Create a new database with versioned structure using NumPy optimization.
    Returns number of documents created.
    """
    # Clear target collection
    target_col.delete_many({})
    print("🧹 Cleared target collection")
    
    created_count = 0
    
    # Convert to numpy arrays for batch processing
    base_names = np.array(list(versioned_groupings.keys()))
    statute_groups = np.array(list(versioned_groupings.values()))
    
    for base_name, statutes in tqdm(zip(base_names, statute_groups), desc="Creating versioned database"):
        # Create a versioned group document
        group_doc = {
            "base_name": base_name,
            "group_id": f"versioned_group_{base_name.lower().replace(' ', '_').replace('-', '_')}",
            "total_versions": len(statutes),
            "versions": []
        }
        
        # Add all versioned statutes to the group
        for statute in statutes:
            # Create a clean version document
            version_doc = {
                "version_label": statute.get("Version_Label", ""),
                "statute_name": statute.get("Statute_Name", ""),
                "date": statute.get("Date", ""),
                "statute_type": statute.get("Statute_Type", ""),
                "province": statute.get("Province", ""),
                "year": statute.get("Year", ""),
                "base_name": statute.get("base_name", ""),
                "sections": statute.get("Sections", []),
                "original_id": str(statute.get("_id", "")),
                # Include all other fields from the original statute
                "act_ordinance": statute.get("Act_Ordinance"),
                "citations": statute.get("Citations"),
                # Add any other fields from the original statute
                "metadata": {
                    k: v for k, v in statute.items() 
                    if k not in ["_id", "Statute_Name", "Date", "Statute_Type", "Sections", "base_name", 
                                "Act_Ordinance", "Citations", "Province", "Year", "Version_Label"]
                }
            }
            group_doc["versions"].append(version_doc)
        
        # Insert the versioned group document
        try:
            target_col.insert_one(group_doc)
            created_count += 1
            metadata["processing_details"]["groups_created"] += 1
        except Exception as e:
            print(f"Error creating versioned group for {base_name}: {e}")
    
    metadata["processing_details"]["database_updates"] = created_count
    return created_count

def save_versioning_info(versioned_groupings: Dict[str, List[Dict]]):
    """
    Save versioning information to JSON file with new naming convention.
    """
    # Prepare data for JSON serialization
    json_data = {}
    for base_name, statutes in versioned_groupings.items():
        json_data[base_name] = []
        for statute in statutes:
            statute_copy = {
                "id": str(statute["_id"]),
                "Statute_Name": statute.get("Statute_Name", ""),
                "Date": statute.get("Date", ""),
                "Version_Label": statute.get("Version_Label", ""),
                "base_name": statute.get("base_name", "")
            }
            json_data[base_name].append(statute_copy)
    
    # New filename pattern
    versioning_filename = f"versioned_statutes_{TARGET_DB}_{TARGET_COLL}_{date.today().isoformat()}.json"
    versioning_path = f"05_statute_versioning/{versioning_filename}"
    with open(versioning_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    print(f"📄 Versioning info saved to: {versioning_path}")

def print_versioning_statistics(versioned_groupings: Dict[str, List[Dict]]):
    """
    Print statistics about the versioning.
    """
    total_statutes = sum(len(statutes) for statutes in versioned_groupings.values())
    multi_version_groups = sum(1 for statutes in versioned_groupings.values() if len(statutes) > 1)
    
    # Count version labels
    version_counts = defaultdict(int)
    for statutes in versioned_groupings.values():
        for statute in statutes:
            version_label = statute.get("Version_Label", "")
            version_counts[version_label] += 1
    
    print("📊 Versioning Statistics:")
    print(f"   - Total base groups: {len(versioned_groupings)}")
    print(f"   - Total statutes: {total_statutes}")
    print(f"   - Groups with multiple versions: {multi_version_groups}")
    print(f"   - Average versions per group: {total_statutes / len(versioned_groupings):.2f}")
    
    print("\n📋 Version Label Distribution:")
    for version_label, count in sorted(version_counts.items()):
        print(f"   - {version_label}: {count} statutes")
    
    # Show some examples
    print("\n📋 Example Versioned Groups:")
    for i, (base_name, statutes) in enumerate(versioned_groupings.items()):
        if len(statutes) > 1:
            print(f"   {base_name}: {len(statutes)} versions")
            for statute in statutes:
                date_str = statute.get("Date", "No date")
                version_label = statute.get("Version_Label", "Unknown")
                print(f"     - {version_label}: {statute.get('Statute_Name', 'Unknown')} ({date_str})")
            print("")
        
        if i >= 4:  # Show only first 5 examples
            break

def validate_versioning(versioned_groupings: Dict[str, List[Dict]]) -> Dict:
    """
    Validate the versioning assignment and return statistics.
    """
    validation_stats = {
        "total_groups": len(versioned_groupings),
        "groups_with_versions": 0,
        "total_versions": 0,
        "date_issues": 0,
        "missing_dates": 0
    }
    
    for base_name, statutes in versioned_groupings.items():
        if len(statutes) > 1:
            validation_stats["groups_with_versions"] += 1
            validation_stats["total_versions"] += len(statutes)
            
            # Check for date issues
            for statute in statutes:
                date_str = statute.get("Date", "")
                if not date_str:
                    validation_stats["missing_dates"] += 1
                elif parser.parse(date_str, fuzzy=True) is None:
                    validation_stats["date_issues"] += 1
    
    return validation_stats

def load_groupings_from_database() -> Dict[str, List[Dict]]:
    """
    Load statute groupings from the specified source collection.
    Each document in the database is a group containing statutes.
    """
    print(f"🔍 Loading grouped statutes from {SOURCE_COLL}...")
    
    # Get group documents from the specified source collection
    groupings = {}
    
    try:
        source_col = source_db[SOURCE_COLL]
        group_documents = list(source_col.find({}))
        
        print(f"📊 Found {len(group_documents)} group documents in {SOURCE_COLL}")
        
        # Convert group documents to the expected format
        for group_doc in group_documents:
            base_name = group_doc.get("base_name", "Unknown")
            statutes = group_doc.get("statutes", [])
            
            # Process ALL groups, even if they don't have statutes yet
            groupings[base_name] = statutes
            if statutes:
                print(f"📋 Group '{base_name}': {len(statutes)} statutes")
            else:
                print(f"📋 Group '{base_name}': No statutes found")
                    
    except Exception as e:
        print(f"⚠️ Error loading from {SOURCE_COLL}: {e}")
        return {}
    
    print(f"📊 Loaded {len(groupings)} unique base groups from {SOURCE_COLL} (including groups without statutes)")
    return groupings

def group_statutes_from_database() -> Dict[str, List[Dict]]:
    """
    Group statutes from database using base_name field.
    This is a fallback for the old database structure.
    """
    print("🔍 Loading statutes from old database structure...")
    statutes = list(source_col.find({}))
    
    # Group by base_name
    groupings = defaultdict(list)
    for statute in statutes:
        base_name = statute.get("base_name", statute.get("Statute_Name", ""))
        if base_name:
            groupings[base_name].append(statute)
    
    print(f"📊 Grouped {len(statutes)} statutes into {len(groupings)} groups")
    return dict(groupings)

def print_comprehensive_metadata():
    """Print comprehensive metadata about the versioning process and save with new naming convention"""
    print(f"\n📊 COMPREHENSIVE VERSIONING METADATA:")
    print("=" * 70)
    print(f"📋 Total groups processed: {metadata['total_groups_processed']}")
    print(f"📋 Total statutes versioned: {metadata['total_statutes_versioned']}")
    print(f"📋 Groups created: {metadata['processing_details']['groups_created']}")
    
    print(f"\n📊 Versioning Statistics:")
    print(f"   - Groups with single version: {metadata['versioning_stats']['groups_with_single_version']}")
    print(f"   - Groups with multiple versions: {metadata['versioning_stats']['groups_with_multiple_versions']}")
    print(f"   - Max versions in a group: {metadata['versioning_stats']['max_versions_in_group']}")
    print(f"   - Average versions per group: {metadata['versioning_stats']['average_versions_per_group']:.2f}")
    print(f"   - Total versions created: {metadata['versioning_stats']['total_versions_created']}")
    
    print(f"\n📊 Processing Details:")
    print(f"   - Statutes with valid dates: {metadata['processing_details']['statutes_with_valid_dates']}")
    print(f"   - Statutes with invalid dates: {metadata['processing_details']['statutes_with_invalid_dates']}")
    print(f"   - Statutes with missing dates: {metadata['processing_details']['statutes_with_missing_dates']}")
    print(f"   - Date parsing errors: {metadata['processing_details']['date_parsing_errors']}")
    print(f"   - Database updates: {metadata['processing_details']['database_updates']}")
    
    print(f"\n📊 GPT Usage Statistics:")
    print(f"   - GPT calls made: {metadata['gpt_usage']['gpt_calls_made']}")
    print(f"   - GPT cache hits: {metadata['gpt_usage']['gpt_cache_hits']}")
    print(f"   - GPT errors: {metadata['gpt_usage']['gpt_errors']}")
    
    print(f"\n📊 Version Label Distribution:")
    for version_label, count in metadata["version_label_distribution"]["version_labels"].most_common():
        print(f"   - {version_label}: {count} statutes")
    
    print(f"\n📊 Sample Versioned Groups:")
    for i, sample_group in enumerate(metadata["version_label_distribution"]["sample_versions"][:10]):
        print(f"   {i+1}. {sample_group['base_name']}: {sample_group['version_count']} versions")
        for version in sample_group['versions']:
            print(f"      - {version['version_label']}: {version['statute_name']} ({version['date']})")
    
    # Calculate and show date range statistics
    print(f"\n📊 Date Range Analysis:")
    date_analysis = metadata["version_label_distribution"]["date_analysis"]
    if date_analysis:
        for base_name, years in list(date_analysis.items())[:10]:
            if years:
                min_year = min(years)
                max_year = max(years)
                span = max_year - min_year
                print(f"   - {base_name}: {min_year}-{max_year} ({span} years, {len(years)} versions)")
    
    # Print GPT ordering decisions
    if metadata["gpt_usage"]["gpt_ordering_decisions"]:
        print(f"\n📊 GPT Ordering Decisions (first 10):")
        for i, decision in enumerate(metadata["gpt_usage"]["gpt_ordering_decisions"][:10]):
            print(f"   {i+1}. {decision['group']}: {decision['statute_a']} vs {decision['statute_b']} -> {decision['gpt_order']}")
    
    # Create metadata folder if it doesn't exist
    os.makedirs("metadata", exist_ok=True)
    
    # New metadata filename pattern
    metadata_filename = f"metadata_versioning_{SOURCE_DB}_{SOURCE_COLL}_{date.today().isoformat()}.json"
    metadata_path = os.path.join("metadata", metadata_filename)
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    print(f"\n📊 Metadata saved to: {metadata_path}")

def main():
    """Main function to assign version labels"""
    print("🚀 Starting statute version assignment with NumPy optimization and GPT integration...")
    
    try:
        # Try to load from the new grouped database structure first
        print("🔍 Attempting to load from grouped database structure...")
        groupings = load_groupings_from_database()
        
        if not groupings:
            print("⚠️ No grouped structure found, trying fallback...")
            # Fallback to old database structure
            groupings = group_statutes_from_database()
        
        if not groupings:
            print("❌ No groupings found. Please run group_statutes_by_base.py first.")
            print("❌ Expected database: Batch-Base-Grouped.statute")
            return
        
        print(f"📊 Processing {len(groupings)} base groups")
        
        # Assign version labels using vectorized operations
        versioned_groupings = assign_version_labels_vectorized(groupings)
        
        # Print statistics
        print_versioning_statistics(versioned_groupings)
        
        # Validate versioning
        validation_stats = validate_versioning(versioned_groupings)
        print(f"📊 Validation: {validation_stats['groups_with_versions']} groups with versions")
        print(f"📊 Validation: {validation_stats['missing_dates']} statutes with missing dates")
        print(f"📊 Validation: {validation_stats['date_issues']} statutes with date parsing issues")
        
        # Create new versioned database using vectorized operations
        created_count = create_versioned_database_vectorized(versioned_groupings)
        print(f"✅ Created {created_count} new versioned groups in the database")
        
        # Save versioning information
        save_versioning_info(versioned_groupings)
        
        # Print comprehensive metadata
        print_comprehensive_metadata()
        
        print("✅ Statute versioning completed with NumPy optimization and GPT integration!")
        print(f"📊 New database: {TARGET_DB}.{TARGET_COLL}")
        print(f"📊 Source database: {SOURCE_DB}.{SOURCE_COLL}")
        
    except Exception as e:
        print(f"❌ Error during statute versioning: {e}")
        raise

if __name__ == "__main__":
    main()
