"""
Advanced script to remove redundant preamble text from other sections within the same statute document.

This version:
1. Handles multiple text fields that might contain preamble content
2. Uses more sophisticated text matching algorithms
3. Provides detailed logging and statistics
4. Can be configured for different text fields
"""

from pymongo import MongoClient
from tqdm import tqdm
import re
import difflib
from typing import List, Dict, Tuple, Optional
import json
from datetime import datetime, date
import os
import numpy as np
from collections import defaultdict, Counter

# --- CONFIG ---
MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "Batched-Statutes"
COLL_NAME = "batch1"

# Text fields to check for preamble content - converted to numpy arrays for faster lookups
TEXT_FIELDS = np.array(["Statute", "Text", "Content", "Definition"])

# Similarity threshold for fuzzy matching
SIMILARITY_THRESHOLD = 0.85

# Initialize metadata tracking
metadata = {
    "total_statutes_processed": 0,
    "statutes_with_preamble": 0,
    "statutes_cleaned": 0,
    "processing_stats": {
        "total_sections_processed": 0,
        "sections_with_duplicates": 0,
        "total_fields_cleaned": 0,
        "total_text_removed": 0
    },
    "duplicate_analysis": {
        "statutes_with_preamble_text": 0,
        "statutes_with_duplicate_sections": 0,
        "total_duplicate_fields_found": 0,
        "preamble_fields_distribution": Counter()
    },
    "cleaning_details": {
        "exact_matches_removed": 0,
        "substring_matches_removed": 0,
        "fuzzy_matches_removed": 0,
        "sample_removals": []
    },
    "field_analysis": {
        "fields_cleaned_by_type": Counter(),
        "text_length_removed_by_field": defaultdict(list)
    }
}

client = MongoClient(MONGO_URI)
col = client[DB_NAME][COLL_NAME]

def normalize_text(text: str) -> str:
    """Normalize text for comparison by removing extra whitespace and converting to lowercase"""
    if not text:
        return ""
    # Remove extra whitespace, newlines, and convert to lowercase
    normalized = re.sub(r'\s+', ' ', text.strip()).lower()
    return normalized

def find_preamble_section(sections: List[Dict]) -> Optional[Dict]:
    """Find the preamble section in the sections array using numpy for faster string operations"""
    for section in sections:
        section_name = section.get("Section", "")
        if isinstance(section_name, str):
            # Use numpy for faster string comparison
            if np.char.equal(section_name.strip().upper(), "PREAMBLE"):
                return section
    return None

def extract_preamble_text(preamble_section: Dict) -> Dict[str, str]:
    """Extract preamble text from all relevant fields using numpy for faster field checking"""
    preamble_texts = {}
    section_fields = np.array(list(preamble_section.keys()))
    text_fields_present = np.intersect1d(section_fields, TEXT_FIELDS)
    
    for field in text_fields_present:
        text = preamble_section.get(field, "")
        if text and isinstance(text, str):
            preamble_texts[field] = text
    return preamble_texts

def calculate_text_similarity(text1: str, text2: str) -> float:
    """Calculate similarity between two texts using difflib"""
    if not text1 or not text2:
        return 0.0
    
    normalized1 = normalize_text(text1)
    normalized2 = normalize_text(text2)
    
    if normalized1 == normalized2:
        return 1.0
    
    matcher = difflib.SequenceMatcher(None, normalized1, normalized2)
    return matcher.ratio()

def remove_preamble_from_text(text: str, preamble_text: str) -> Tuple[str, bool, str]:
    """
    Remove preamble text from the given text.
    Returns (cleaned_text, was_modified, removal_type)
    """
    if not text or not preamble_text:
        return text, False, "none"
    
    normalized_text = normalize_text(text)
    normalized_preamble = normalize_text(preamble_text)
    
    # Exact match
    if normalized_text == normalized_preamble:
        return "", True, "exact"
    
    # Substring match
    if normalized_preamble in normalized_text:
        # Find the actual preamble text in the original text (case-insensitive)
        pattern = re.compile(re.escape(preamble_text), re.IGNORECASE)
        cleaned_text = pattern.sub('', text)
        # Clean up extra whitespace
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
        return cleaned_text, True, "substring"
    
    # Fuzzy match
    similarity = calculate_text_similarity(text, preamble_text)
    if similarity >= SIMILARITY_THRESHOLD:
        # For high similarity, remove the preamble-like content
        # This is a simplified approach - in practice you might want more sophisticated logic
        return "", True, "fuzzy"
    
    return text, False, "none"

def clean_section_text_fields(section: Dict, preamble_texts: Dict[str, str]) -> Tuple[Dict, int, Dict]:
    """
    Clean preamble text from all relevant fields in a section.
    Returns (cleaned_section, number_of_fields_cleaned, removal_details)
    """
    cleaned_section = section.copy()
    fields_cleaned = 0
    removal_details = {
        "exact_matches": 0,
        "substring_matches": 0,
        "fuzzy_matches": 0,
        "text_removed_by_field": {}
    }
    
    for field in TEXT_FIELDS:
        if field in preamble_texts and field in cleaned_section:
            original_text = cleaned_section[field]
            if isinstance(original_text, str):
                original_length = len(original_text)
                cleaned_text, was_modified, removal_type = remove_preamble_from_text(original_text, preamble_texts[field])
                if was_modified:
                    cleaned_section[field] = cleaned_text
                    fields_cleaned += 1
                    removal_details[removal_type + "_matches"] += 1
                    text_removed = original_length - len(cleaned_text)
                    removal_details["text_removed_by_field"][field] = text_removed
                    metadata["field_analysis"]["text_length_removed_by_field"][field].append(text_removed)
    
    return cleaned_section, fields_cleaned, removal_details

def clean_statute_sections(statute: Dict) -> Tuple[Dict, Dict]:
    """
    Clean redundant preamble text from all sections except the preamble section itself.
    Returns (cleaned_statute, statistics)
    """
    sections = statute.get("Sections", [])
    if not sections:
        return statute, {"sections_cleaned": 0, "fields_cleaned": 0, "total_text_removed": 0}
    
    # Find the preamble section
    preamble_section = find_preamble_section(sections)
    if not preamble_section:
        return statute, {"sections_cleaned": 0, "fields_cleaned": 0, "total_text_removed": 0}
    
    # Extract preamble text from all relevant fields
    preamble_texts = extract_preamble_text(preamble_section)
    if not preamble_texts:
        return statute, {"sections_cleaned": 0, "fields_cleaned": 0, "total_text_removed": 0}
    
    cleaned_sections = []
    sections_cleaned = 0
    total_fields_cleaned = 0
    total_text_removed = 0
    
    for section in sections:
        # Skip the preamble section itself
        if section.get("Section", "").strip().upper() == "PREAMBLE":
            cleaned_sections.append(section)
            continue
        
        # Clean the section
        cleaned_section, fields_cleaned, removal_details = clean_section_text_fields(section, preamble_texts)
        if fields_cleaned > 0:
            sections_cleaned += 1
            total_fields_cleaned += fields_cleaned
            total_text_removed += sum(removal_details["text_removed_by_field"].values())
            
            # Track removal types
            metadata["cleaning_details"]["exact_matches_removed"] += removal_details["exact_matches"]
            metadata["cleaning_details"]["substring_matches_removed"] += removal_details["substring_matches"]
            metadata["cleaning_details"]["fuzzy_matches_removed"] += removal_details["fuzzy_matches"]
        
        cleaned_sections.append(cleaned_section)
    
    cleaned_statute = statute.copy()
    cleaned_statute["Sections"] = cleaned_sections
    
    stats = {
        "sections_cleaned": sections_cleaned,
        "fields_cleaned": total_fields_cleaned,
        "total_text_removed": total_text_removed
    }
    
    return cleaned_statute, stats

def analyze_statute_preamble_usage(statute: Dict) -> Dict:
    """Analyze how much preamble content is duplicated in other sections"""
    sections = statute.get("Sections", [])
    preamble_section = find_preamble_section(sections)
    
    if not preamble_section:
        return {"has_preamble": False}
    
    preamble_texts = extract_preamble_text(preamble_section)
    if not preamble_texts:
        return {"has_preamble": True, "preamble_has_text": False}
    
    analysis = {
        "has_preamble": True,
        "preamble_has_text": True,
        "total_sections": len(sections),
        "sections_with_duplicates": 0,
        "total_duplicate_fields": 0,
        "preamble_fields": list(preamble_texts.keys())
    }
    
    for section in sections:
        if section.get("Section", "").strip().upper() == "PREAMBLE":
            continue
        
        section_has_duplicates = False
        for field in TEXT_FIELDS:
            if field in preamble_texts and field in section:
                text = section[field]
                if isinstance(text, str):
                    similarity = calculate_text_similarity(text, preamble_texts[field])
                    if similarity >= SIMILARITY_THRESHOLD:
                        section_has_duplicates = True
                        analysis["total_duplicate_fields"] += 1
        
        if section_has_duplicates:
            analysis["sections_with_duplicates"] += 1
    
    return analysis

def main():
    """Main processing function"""
    print("🔍 Scanning for statutes with preamble sections...")
    
    # Get all statutes
    statutes = list(col.find({}))
    total_statutes = len(statutes)
    
    print(f"📊 Processing {total_statutes} statutes...")
    
    # Analysis phase
    print("\n📈 Analyzing preamble usage...")
    statutes_with_preamble = 0
    total_duplicate_sections = 0
    total_duplicate_fields = 0
    
    for statute in tqdm(statutes, desc="Analyzing"):
        metadata["total_statutes_processed"] += 1
        analysis = analyze_statute_preamble_usage(statute)
        if analysis["has_preamble"]:
            statutes_with_preamble += 1
            metadata["statutes_with_preamble"] += 1
            
            if analysis["preamble_has_text"]:
                metadata["duplicate_analysis"]["statutes_with_preamble_text"] += 1
                
                # Track preamble fields distribution
                for field in analysis["preamble_fields"]:
                    metadata["duplicate_analysis"]["preamble_fields_distribution"][field] += 1
            
            if analysis["sections_with_duplicates"] > 0:
                metadata["duplicate_analysis"]["statutes_with_duplicate_sections"] += 1
                metadata["duplicate_analysis"]["total_duplicate_fields_found"] += analysis["total_duplicate_fields"]
            
            total_duplicate_sections += analysis["sections_with_duplicates"]
            total_duplicate_fields += analysis["total_duplicate_fields"]
    
    print(f"\n📊 Analysis Results:")
    print(f"   - Statutes with preamble sections: {statutes_with_preamble}")
    print(f"   - Total sections with duplicates: {total_duplicate_sections}")
    print(f"   - Total duplicate fields: {total_duplicate_fields}")
    
    # Processing phase
    print(f"\n🧹 Cleaning preamble duplicates...")
    processed_count = 0
    total_sections_cleaned = 0
    total_fields_cleaned = 0
    total_text_removed = 0
    
    for statute in tqdm(statutes, desc="Cleaning"):
        analysis = analyze_statute_preamble_usage(statute)
        if analysis["has_preamble"] and analysis["sections_with_duplicates"] > 0:
            cleaned_statute, stats = clean_statute_sections(statute)
            total_sections_cleaned += stats["sections_cleaned"]
            total_fields_cleaned += stats["fields_cleaned"]
            total_text_removed += stats["total_text_removed"]
            
            # Update the document in the database
            col.replace_one({"_id": statute["_id"]}, cleaned_statute)
            processed_count += 1
            metadata["statutes_cleaned"] += 1
    
    # Update processing stats
    metadata["processing_stats"]["total_sections_processed"] = sum(len(s.get("Sections", [])) for s in statutes)
    metadata["processing_stats"]["sections_with_duplicates"] = total_duplicate_sections
    metadata["processing_stats"]["total_fields_cleaned"] = total_fields_cleaned
    metadata["processing_stats"]["total_text_removed"] = total_text_removed
    
    # Calculate text length statistics
    for field_name, lengths in metadata["field_analysis"]["text_length_removed_by_field"].items():
        if lengths:
            metadata["field_analysis"]["text_length_removed_by_field"][field_name] = {
                "min": min(lengths),
                "max": max(lengths),
                "avg": sum(lengths) / len(lengths),
                "total": sum(lengths),
                "count": len(lengths)
            }
    
    print(f"\n📊 PREAMBLE DUPLICATE REMOVAL METADATA:")
    print("=" * 50)
    print(f"📋 Total statutes processed: {metadata['total_statutes_processed']}")
    print(f"📋 Statutes with preamble sections: {metadata['statutes_with_preamble']}")
    print(f"📋 Statutes cleaned: {metadata['statutes_cleaned']}")
    print(f"📋 Total sections processed: {metadata['processing_stats']['total_sections_processed']}")
    print(f"📋 Sections with duplicates: {metadata['processing_stats']['sections_with_duplicates']}")
    print(f"📋 Total fields cleaned: {metadata['processing_stats']['total_fields_cleaned']}")
    print(f"📋 Total text removed: {metadata['processing_stats']['total_text_removed']} characters")
    
    print(f"\n📊 Duplicate Analysis:")
    print(f"   - Statutes with preamble text: {metadata['duplicate_analysis']['statutes_with_preamble_text']}")
    print(f"   - Statutes with duplicate sections: {metadata['duplicate_analysis']['statutes_with_duplicate_sections']}")
    print(f"   - Total duplicate fields found: {metadata['duplicate_analysis']['total_duplicate_fields_found']}")
    
    print(f"\n📊 Preamble Fields Distribution:")
    for field_name, count in metadata["duplicate_analysis"]["preamble_fields_distribution"].most_common():
        print(f"   - {field_name}: {count} times")
    
    print(f"\n📊 Cleaning Details:")
    print(f"   - Exact matches removed: {metadata['cleaning_details']['exact_matches_removed']}")
    print(f"   - Substring matches removed: {metadata['cleaning_details']['substring_matches_removed']}")
    print(f"   - Fuzzy matches removed: {metadata['cleaning_details']['fuzzy_matches_removed']}")
    
    print(f"\n📊 Text Removal by Field:")
    for field_name, stats in metadata["field_analysis"]["text_length_removed_by_field"].items():
        if isinstance(stats, dict):
            print(f"   - {field_name}: {stats['total']} chars removed ({stats['count']} fields)")
    
    # Add script/db/collection/date info to metadata
    metadata["script"] = "remove_preamble_duplicates_advanced.py"
    metadata["db_name"] = DB_NAME
    metadata["collection"] = COLL_NAME
    metadata["date"] = date.today().isoformat()

    # Save metadata to metadata/ folder with new naming convention
    metadata_dir = "metadata"
    os.makedirs(metadata_dir, exist_ok=True)
    meta_filename = f"metadata_remove_preamble_duplicates_advanced_{DB_NAME}_{COLL_NAME}_{date.today().isoformat()}.json"
    meta_path = os.path.join(metadata_dir, meta_filename)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Processing complete!")
    print(f"   - Total statutes processed: {total_statutes}")
    print(f"   - Statutes with preamble sections: {statutes_with_preamble}")
    print(f"   - Statutes cleaned: {processed_count}")
    print(f"   - Total sections cleaned: {total_sections_cleaned}")
    print(f"   - Total fields cleaned: {total_fields_cleaned}")
    print(f"   - Total text removed: {total_text_removed} characters")
    print(f"📊 Metadata saved to {meta_path}")

if __name__ == "__main__":
    main() 