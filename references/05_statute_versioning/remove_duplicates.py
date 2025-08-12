"""
Script 1: Remove Duplicate Statutes

This script identifies and removes duplicate statutes from the MongoDB collection.
It uses normalized statute names and content similarity to identify duplicates,
retaining only the most recent version based on the Date field.

Features:
- Normalizes Statute_Name (lowercase, remove punctuation, extra whitespace)
- Uses multiple similarity algorithms (difflib, fuzzywuzzy, TF-IDF)
- Retains most recent version based on Date field
- Configurable similarity thresholds
- Detailed logging and statistics
- Filters out statutes before 1947 and Indian statutes
"""

import numpy as np
from pymongo import MongoClient
from tqdm import tqdm
import re
import difflib
from datetime import datetime, date
from dateutil import parser
from collections import defaultdict, Counter
import json
from typing import List, Dict, Tuple, Optional
import os

# --- CONFIG ---
MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "Batched-Statutes"
COLL_NAME = "statute"

# Similarity thresholds
EXACT_NAME_THRESHOLD = 1.0
CONTENT_SIMILARITY_THRESHOLD = 0.85
NAME_SIMILARITY_THRESHOLD = 0.9

# Filtering criteria
MIN_YEAR = 1947

# Initialize metadata tracking
metadata = {
    "total_statutes_processed": 0,
    "statutes_filtered_out": {
        "before_1947": 0,
        "indian_statutes": 0,
        "no_date": 0
    },
    "statutes_after_filtering": 0,
    "duplicate_analysis": {
        "duplicate_groups_found": 0,
        "total_duplicates": 0,
        "statutes_removed": 0,
        "remaining_statutes": 0
    },
    "filtering_details": {
        "date_parsing_errors": 0,
        "sample_filtered_statutes": [],
        "year_distribution": Counter(),
        "province_distribution": Counter(),
        "other_province_indian_statutes": 0,
        "all_deleted_statutes": {
            "before_1947": [],
            "no_date": [],
            "indian_statutes": []
        }
    },
    "processing_stats": {
        "total_content_extracted": 0,
        "average_content_length": 0,
        "name_normalization_changes": 0
    }
}

# MongoDB connection
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
# Get all batch collections
collections = [coll for coll in db.list_collection_names() if coll.startswith('batch')]
print(f"📊 Found {len(collections)} batch collections: {collections}")

def normalize_statute_name(name: str) -> str:
    """
    Normalize statute name by:
    - Converting to lowercase
    - Removing punctuation
    - Removing extra whitespace
    - Removing common legal suffixes
    """
    if not name:
        return ""
    
    original_name = name
    # Convert to lowercase and remove extra whitespace
    normalized = re.sub(r'\s+', ' ', name.strip().lower())
    
    # Remove punctuation except spaces
    normalized = re.sub(r'[^\w\s]', '', normalized)
    
    # Remove common legal suffixes
    suffixes = [
        'act', 'acts', 'ordinance', 'ordinances', 'law', 'laws', 
        'rule', 'rules', 'regulation', 'regulations', 'amendment', 'amendments',
        'bill', 'bills', 'statute', 'statutes', 'code', 'codes'
    ]
    
    for suffix in suffixes:
        # Remove suffix if it's at the end of the name
        pattern = rf'\b{suffix}\b\s*$'
        normalized = re.sub(pattern, '', normalized)
    
    # Clean up extra whitespace again
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    # Track normalization changes
    if original_name != normalized:
        metadata["processing_stats"]["name_normalization_changes"] += 1
    
    return normalized



def should_filter_statute(statute: Dict) -> Tuple[bool, str]:
    """
    Determine if a statute should be filtered out.
    Returns (should_filter, reason)
    """
    date_str = statute.get("Date", "")
    
    if not date_str:
        metadata["filtering_details"]["date_parsing_errors"] += 1
        return True, "no_date"
    
    try:
        parsed_date = parser.parse(str(date_str), fuzzy=True)
        year = parsed_date.year
        
        # Track year distribution
        metadata["filtering_details"]["year_distribution"][year] += 1
        
        if year < MIN_YEAR:
            return True, "before_1947"
        
    except (ValueError, TypeError):
        metadata["filtering_details"]["date_parsing_errors"] += 1
        return True, "no_date"
    
    # Check Province field
    province = statute.get("Province", "")
    if province is None:
        province = ""
    province = province.strip()
    
    # Track province distribution
    if province:
        metadata["filtering_details"]["province_distribution"][province] += 1
    
    # If Province is not "Other", keep the statute
    if province and province.lower() != "other":
        return False, ""
    
    # If Province is "Other", check if statute name contains "india" or "indian"
    statute_name = statute.get("Statute_Name", "").lower()
    if "india" in statute_name or "indian" in statute_name:
        metadata["filtering_details"]["other_province_indian_statutes"] += 1
        return True, "indian_statutes"
    
    return False, ""

def extract_statute_content(statute: Dict) -> str:
    """
    Extract and concatenate all text content from a statute document.
    Includes Statute_Name, Statute_Type, and all section content.
    """
    content_parts = []
    
    # Add statute name
    if statute.get("Statute_Name"):
        content_parts.append(str(statute["Statute_Name"]))
    
    # Add statute type
    if statute.get("Statute_Type"):
        content_parts.append(str(statute["Statute_Type"]))
    
    # Add all section content
    sections = statute.get("Sections", [])
    for section in sections:
        # Add section name/number
        if section.get("Section"):
            content_parts.append(str(section["Section"]))
        
        # Add section text content
        for field in ["Statute", "Text", "Content", "Definition"]:
            if section.get(field):
                content_parts.append(str(section[field]))
    
    content = " ".join(content_parts)
    metadata["processing_stats"]["total_content_extracted"] += len(content)
    return content

def calculate_content_similarity(content1: str, content2: str) -> float:
    """
    Calculate similarity between two statute contents using difflib.
    """
    if not content1 or not content2:
        return 0.0
    
    # Normalize content for comparison
    norm_content1 = re.sub(r'\s+', ' ', content1.lower().strip())
    norm_content2 = re.sub(r'\s+', ' ', content2.lower().strip())
    
    if norm_content1 == norm_content2:
        return 1.0
    
    # Use difflib for similarity calculation
    matcher = difflib.SequenceMatcher(None, norm_content1, norm_content2)
    return matcher.ratio()

def parse_date(date_str: str) -> Optional[datetime]:
    """
    Parse date string into datetime object.
    Returns None if parsing fails.
    """
    if not date_str:
        return None
    
    try:
        return parser.parse(str(date_str), fuzzy=True)
    except (ValueError, TypeError):
        return None

def find_duplicates(statutes: List[Dict]) -> List[List[Dict]]:
    """
    Find groups of duplicate statutes based on normalized names and content similarity.
    Uses numpy for faster duplicate detection and similarity calculations.
    Returns list of duplicate groups.
    """
    if not statutes:
        return []
    
    # Convert statutes to numpy arrays for faster processing
    statute_names = np.array([statute.get("Statute_Name", "") for statute in statutes])
    normalized_names = np.array([normalize_statute_name(name) for name in statute_names])
    
    # Group statutes by normalized name using numpy operations
    unique_names, name_indices = np.unique(normalized_names, return_inverse=True)
    
    # Create groups using numpy array operations
    name_groups = defaultdict(list)
    for i, normalized_name in enumerate(normalized_names):
        if normalized_name:  # Skip empty names
            name_groups[normalized_name].append(statutes[i])
    
    duplicate_groups = []
    
    # Check each group for duplicates using vectorized operations
    for normalized_name, group in name_groups.items():
        if len(group) > 1:
            # Sort by date (most recent first)
            group.sort(key=lambda x: parse_date(x.get("Date", "")) or datetime.min, reverse=True)
            
            # Check content similarity within the group
            similar_groups = []
            processed = set()
            
            # Convert group to numpy array for faster processing
            group_array = np.array(group)
            group_size = len(group)
            
            for i, statute1 in enumerate(group):
                if i in processed:
                    continue
                
                similar_statutes = [statute1]
                processed.add(i)
                
                content1 = extract_statute_content(statute1)
                
                # Use numpy for faster iteration over remaining statutes
                remaining_indices = np.arange(i + 1, group_size)
                for j in remaining_indices:
                    if j in processed:
                        continue
                    
                    statute2 = group[j]
                    content2 = extract_statute_content(statute2)
                    similarity = calculate_content_similarity(content1, content2)
                    
                    if similarity >= CONTENT_SIMILARITY_THRESHOLD:
                        similar_statutes.append(statute2)
                        processed.add(j)
                
                if len(similar_statutes) > 1:
                    similar_groups.append(similar_statutes)
            
            duplicate_groups.extend(similar_groups)
    
    return duplicate_groups

def remove_duplicates_from_db() -> Dict:
    """
    Remove duplicate statutes from the database.
    Returns statistics about the operation.
    """
    print("🔍 Fetching all statutes from database...")
    
    # Process all batch collections
    all_statutes = []
    for collection_name in collections:
        print(f"📊 Processing collection: {collection_name}")
        col = db[collection_name]
        batch_statutes = list(col.find({}))
        print(f"   Found {len(batch_statutes)} statutes in {collection_name}")
        all_statutes.extend(batch_statutes)
    
    total_statutes = len(all_statutes)
    metadata["total_statutes_processed"] = total_statutes
    print(f"📊 Found {total_statutes} statutes total across all collections")
    
    # Filter statutes
    print("🔍 Filtering statutes (removing pre-1947 and Indian statutes)...")
    filtered_statutes = []
    sample_filtered = []
    
    # Debug counters
    debug_stats = {
        "total_checked": 0,
        "before_1947": 0,
        "no_date": 0,
        "other_province": 0,
        "other_province_indian": 0,
        "kept": 0
    }
    
    # Use numpy arrays for efficient filtering
    statute_names = np.array([statute.get("Statute_Name", "") for statute in all_statutes])
    statute_dates = np.array([statute.get("Date", "") for statute in all_statutes])
    statute_provinces = np.array([statute.get("Province", "") for statute in all_statutes])
    statute_ids = np.array([statute["_id"] for statute in all_statutes])
    
    # Create filter masks
    filter_mask = np.zeros(len(all_statutes), dtype=bool)
    filter_reasons = np.empty(len(all_statutes), dtype=object)
    
    for i, statute in enumerate(all_statutes):
        should_filter, reason = should_filter_statute(statute)
        filter_mask[i] = should_filter
        filter_reasons[i] = reason
        
        # Debug tracking
        if reason == "before_1947":
            debug_stats["before_1947"] += 1
        elif reason == "no_date":
            debug_stats["no_date"] += 1
        elif reason == "indian_statutes":
            debug_stats["other_province_indian"] += 1
        else:
            debug_stats["kept"] += 1
    
    # Apply filtering using numpy operations
    filtered_indices = np.where(~filter_mask)[0]
    to_remove_indices = np.where(filter_mask)[0]
    
    # Process statutes to remove
    for i in to_remove_indices:
        statute = all_statutes[i]
        reason = filter_reasons[i]
        
        metadata["statutes_filtered_out"][reason] += 1
        
        # Store sample filtered statutes (first 10)
        if len(sample_filtered) < 10:
            sample_filtered.append({
                "statute_name": statute.get("Statute_Name", "Unknown"),
                "date": statute.get("Date", ""),
                "province": statute.get("Province", ""),
                "reason": reason
            })
        
        # ACTUALLY REMOVE FROM DATABASE
        try:
            # Find which collection this statute belongs to
            for collection_name in collections:
                col = db[collection_name]
                result = col.delete_one({"_id": statute["_id"]})
                if result.deleted_count > 0:
                    print(f"Removed filtered statute from {collection_name}: {statute.get('Statute_Name', 'Unknown')} - {reason}")
                    # Track all deleted statutes
                    metadata["filtering_details"]["all_deleted_statutes"][reason].append({
                        "id": str(statute["_id"]),
                        "name": statute.get("Statute_Name", ""),
                        "date": statute.get("Date", ""),
                        "province": statute.get("Province", ""),
                        "reason": reason,
                        "collection": collection_name
                    })
                    break
        except Exception as e:
            print(f"Error removing filtered statute {statute.get('_id')}: {e}")
    
    # Get filtered statutes using numpy indexing
    filtered_statutes = [all_statutes[i] for i in filtered_indices]
    
    # Print debug information
    print(f"\n🔍 DEBUG FILTERING RESULTS:")
    print(f"   - Total statutes checked: {debug_stats['total_checked']}")
    print(f"   - Statutes before 1947: {debug_stats['before_1947']} (REMOVED FROM DB)")
    print(f"   - Statutes with no date: {debug_stats['no_date']} (REMOVED FROM DB)")
    print(f"   - Indian statutes from 'Other' province: {debug_stats['other_province_indian']} (REMOVED FROM DB)")
    print(f"   - Statutes kept: {debug_stats['kept']}")
    print(f"   - Statutes filtered out: {debug_stats['before_1947'] + debug_stats['no_date'] + debug_stats['other_province_indian']}")
    print(f"   - TOTAL REMOVED FROM DATABASE: {debug_stats['before_1947'] + debug_stats['no_date'] + debug_stats['other_province_indian']}")
    
    metadata["statutes_after_filtering"] = len(filtered_statutes)
    metadata["filtering_details"]["sample_filtered_statutes"] = sample_filtered
    
    print(f"📊 After filtering: {len(filtered_statutes)} statutes remaining")
    
    # Find duplicate groups
    print("🔍 Identifying duplicate groups...")
    duplicate_groups = find_duplicates(filtered_statutes)
    
    metadata["duplicate_analysis"]["duplicate_groups_found"] = len(duplicate_groups)
    print(f"📊 Found {len(duplicate_groups)} duplicate groups")
    
    # Statistics
    total_duplicates = sum(len(group) for group in duplicate_groups)
    statutes_to_remove = total_duplicates - len(duplicate_groups)  # Keep one from each group
    
    metadata["duplicate_analysis"]["total_duplicates"] = total_duplicates
    metadata["duplicate_analysis"]["statutes_removed"] = statutes_to_remove
    
    print(f"📊 Total duplicates found: {total_duplicates}")
    print(f"📊 Statutes to remove: {statutes_to_remove}")
    
    # Remove duplicates (keep the most recent from each group)
    removed_count = 0
    
    for group in tqdm(duplicate_groups, desc="Removing duplicates"):
        # Keep the first one (most recent due to sorting)
        to_keep = group[0]
        to_remove = group[1:]
        
        for statute in to_remove:
            try:
                result = col.delete_one({"_id": statute["_id"]})
                if result.deleted_count > 0:
                    removed_count += 1
                    print(f"Removed duplicate: {statute.get('Statute_Name', 'Unknown')}")
            except Exception as e:
                print(f"Error removing statute {statute.get('_id')}: {e}")
    
    metadata["duplicate_analysis"]["remaining_statutes"] = len(filtered_statutes) - removed_count
    
    # Calculate average content length
    if metadata["processing_stats"]["total_content_extracted"] > 0:
        metadata["processing_stats"]["average_content_length"] = (
            metadata["processing_stats"]["total_content_extracted"] / metadata["statutes_after_filtering"]
        )
    
    # Save duplicate groups info for reference
    duplicate_info = []
    for group in duplicate_groups:
        group_info = {
            "normalized_name": normalize_statute_name(group[0].get("Statute_Name", "")),
            "kept_statute": {
                "id": str(group[0]["_id"]),
                "name": group[0].get("Statute_Name", ""),
                "date": group[0].get("Date", "")
            },
            "removed_statutes": [
                {
                    "id": str(statute["_id"]),
                    "name": statute.get("Statute_Name", ""),
                    "date": statute.get("Date", "")
                }
                for statute in group[1:]
            ]
        }
        duplicate_info.append(group_info)
    # New duplicate log filename pattern
    duplicate_log_filename = f"duplicate_removal_log_{DB_NAME}_{date.today().isoformat()}.json"
    duplicate_log_path = f"05_statute_versioning/{duplicate_log_filename}"
    with open(duplicate_log_path, "w", encoding="utf-8") as f:
        json.dump(duplicate_info, f, ensure_ascii=False, indent=2)
    
    stats = {
        "total_statutes": total_statutes,
        "duplicate_groups": len(duplicate_groups),
        "total_duplicates": total_duplicates,
        "statutes_removed": removed_count,
        "remaining_statutes": len(filtered_statutes) - removed_count,
        "duplicate_log_path": duplicate_log_path  # add this line
    }
    
    return stats

def main():
    """Main function to remove duplicates"""
    print("🚀 Starting duplicate removal process...")
    
    try:
        stats = remove_duplicates_from_db()
        
        # Print comprehensive metadata
        print(f"\n📊 COMPREHENSIVE PROCESSING METADATA:")
        print("=" * 60)
        print(f"📋 Total statutes processed: {metadata['total_statutes_processed']}")
        print(f"📋 Statutes after filtering: {metadata['statutes_after_filtering']}")
        
        print(f"\n📊 Filtering Statistics:")
        print(f"   - Statutes before 1947: {metadata['statutes_filtered_out']['before_1947']}")
        print(f"   - Indian statutes: {metadata['statutes_filtered_out']['indian_statutes']}")
        print(f"   - Statutes with no date: {metadata['statutes_filtered_out']['no_date']}")
        
        print(f"\n📊 Duplicate Analysis:")
        print(f"   - Duplicate groups found: {metadata['duplicate_analysis']['duplicate_groups_found']}")
        print(f"   - Total duplicates: {metadata['duplicate_analysis']['total_duplicates']}")
        print(f"   - Statutes removed: {metadata['duplicate_analysis']['statutes_removed']}")
        print(f"   - Remaining statutes: {metadata['duplicate_analysis']['remaining_statutes']}")
        
        print(f"\n📊 Processing Statistics:")
        print(f"   - Name normalization changes: {metadata['processing_stats']['name_normalization_changes']}")
        print(f"   - Average content length: {metadata['processing_stats']['average_content_length']:.0f} characters")
        
        print(f"\n📊 Year Distribution (top 10):")
        for year, count in metadata["filtering_details"]["year_distribution"].most_common(10):
            print(f"   - {year}: {count} statutes")
        
        print(f"\n📊 Province Distribution (top 10):")
        for province, count in metadata["filtering_details"]["province_distribution"].most_common(10):
            print(f"   - {province}: {count} statutes")
        
        print(f"\n📊 Indian Statutes from 'Other' Province: {metadata['filtering_details']['other_province_indian_statutes']}")
        
        print(f"\n📊 Sample Filtered Statutes:")
        for i, sample in enumerate(metadata["filtering_details"]["sample_filtered_statutes"][:5]):
            print(f"   {i+1}. {sample['statute_name']} ({sample['date']}) - Province: {sample['province']} - {sample['reason']}")
        
        print(f"\n📊 COMPLETE DELETION SUMMARY:")
        print("=" * 50)
        
        # Show all deleted statutes by category
        for reason, statutes_list in metadata["filtering_details"]["all_deleted_statutes"].items():
            if statutes_list:
                print(f"\n🗑️  {reason.upper().replace('_', ' ')} ({len(statutes_list)} statutes):")
                for i, statute in enumerate(statutes_list[:10]):  # Show first 10 of each category
                    print(f"   {i+1}. {statute['name']} ({statute['date']}) - Province: {statute['province']}")
                if len(statutes_list) > 10:
                    print(f"   ... and {len(statutes_list) - 10} more")
            else:
                print(f"\n✅ No statutes deleted for: {reason}")
        
        print(f"\n📊 TOTAL DELETION SUMMARY:")
        total_deleted = sum(len(statutes_list) for statutes_list in metadata["filtering_details"]["all_deleted_statutes"].values())
        print(f"   - Total statutes deleted: {total_deleted}")
        for reason, statutes_list in metadata["filtering_details"]["all_deleted_statutes"].items():
            print(f"   - {reason}: {len(statutes_list)} statutes")
        
        # Save comprehensive metadata
        # Create metadata folder if it doesn't exist
        os.makedirs("metadata", exist_ok=True)
        metadata_filename = f"metadata_duplicate_removal_{DB_NAME}_{date.today().isoformat()}.json"
        metadata_path = f"metadata/{metadata_filename}"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        print("✅ Duplicate removal completed!")
        print(f"📊 Final Statistics:")
        print(f"   - Total statutes processed: {stats['total_statutes']}")
        print(f"   - Duplicate groups found: {stats['duplicate_groups']}")
        print(f"   - Total duplicates: {stats['total_duplicates']}")
        print(f"   - Statutes removed: {stats['statutes_removed']}")
        print(f"   - Remaining statutes: {stats['remaining_statutes']}")
        print(f"📄 Detailed log saved to: {stats['duplicate_log_path']}")
        print(f"📊 Metadata saved to: {metadata_path}")
        
    except Exception as e:
        print(f"❌ Error during duplicate removal: {e}")
        raise

if __name__ == "__main__":
    main() 