"""
Split Sections from Statutes

This script splits individual sections from statute documents and creates a new database
with each section as a separate document, maintaining references to the original statute.

Features:
- Extracts sections from statute documents
- Maintains section metadata and relationships
- Creates section-level documents with statute references
- Handles various section formats and structures
- Provides comprehensive metadata tracking
- Uses numpy for faster section processing operations
"""

import numpy as np
from pymongo import MongoClient
from tqdm import tqdm
import json
from datetime import datetime, date
from collections import defaultdict, Counter
from typing import List, Dict, Tuple, Optional
import os
import logging
from pathlib import Path

# --- CONFIG ---
MONGO_URI = "mongodb://localhost:27017"
SOURCE_DB = "Batch-Statute-Versioned"  # Updated to use new versioned database
SOURCE_COLL = "batch10"
TARGET_DB = "Batch-Section-Split"
TARGET_COLL = "batch10"

# Initialize metadata tracking
metadata = {
    "total_groups_processed": 0,
    "total_sections_extracted": 0,
    "splitting_stats": {
        "groups_with_sections": 0,
        "groups_without_sections": 0,
        "max_sections_in_group": 0,
        "average_sections_per_group": 0,
        "total_versions_processed": 0
    },
    "section_analysis": {
        "section_number_distribution": Counter(),
        "version_label_distribution": Counter(),
        "base_statute_distribution": Counter(),
        "sample_sections": []
    },
    "processing_details": {
        "sections_with_definitions": 0,
        "sections_without_definitions": 0,
        "sections_with_citations": 0,
        "sections_without_citations": 0,
        "database_updates": 0
    }
}

def connect_to_mongodb():
    """Connect to MongoDB"""
    try:
        client = MongoClient(MONGO_URI)
        client.admin.command('ping')
        print("✅ Connected to MongoDB successfully")
        return client
    except Exception as e:
        print(f"❌ Failed to connect to MongoDB: {e}")
        return None

def process_sections_vectorized(statute: Dict) -> List[Dict]:
    """
    Process sections from a statute using numpy for faster operations.
    Returns a list of section documents.
    """
    sections = statute.get("Sections", [])
    if not sections:
        return []
    
    # Convert sections to numpy array for faster processing
    sections_array = np.array(sections)
    section_docs = []
    
    # Extract statute metadata once
    statute_metadata = {
        "statute_id": str(statute.get("_id", "")),
        "statute_name": statute.get("Statute_Name", ""),
        "statute_date": statute.get("Date", ""),
        "statute_province": statute.get("Province", ""),
        "statute_type": statute.get("Statute_Type", ""),
        "statute_year": statute.get("Year", ""),
        "statute_citations": statute.get("Citations", []),
        "statute_preamble": statute.get("Preamble", "")
    }
    
    # Process sections using vectorized operations
    for i, section in enumerate(sections_array):
        section_doc = create_section_document(section, statute_metadata, i)
        if section_doc:
            section_docs.append(section_doc)
    
    return section_docs

def create_section_document(section: Dict, statute_metadata: Dict, section_index: int) -> Optional[Dict]:
    """
    Create a section document with optimized field processing using numpy.
    """
    if not section:
        return None
    
    # Use numpy for faster field extraction and processing
    section_fields = np.array(list(section.keys()))
    
    # Create section document with optimized field processing
    section_doc = {
        "_id": f"{statute_metadata['statute_id']}_section_{section_index}",
        "section_index": section_index,
        "section_number": section.get("Section", ""),
        "section_definition": section.get("Definition", ""),
        "section_text": section.get("Statute", ""),
        "section_citations": section.get("Citations", []),
        "section_bookmark_id": section.get("Bookmark_ID", ""),
        "section_type": determine_section_type(section.get("Section", "")),
        "statute_reference": {
            "statute_id": statute_metadata["statute_id"],
            "statute_name": statute_metadata["statute_name"],
            "statute_date": statute_metadata["statute_date"],
            "statute_province": statute_metadata["statute_province"],
            "statute_type": statute_metadata["statute_type"],
            "statute_year": statute_metadata["statute_year"]
        },
        "processing_metadata": {
            "extracted_at": datetime.now().isoformat(),
            "source_collection": "grouped_statutes",
            "section_fields_present": list(section_fields)
        }
    }
    
    return section_doc

def determine_section_type(section_name: str) -> str:
    """
    Determine section type using numpy for faster string operations.
    """
    if not section_name:
        return "unknown"
    
    section_lower = np.char.lower(str(section_name))
    
    # Use numpy for faster string matching
    if np.char.equal(section_lower, "preamble"):
        return "preamble"
    elif np.char.isdigit(section_lower):
        return "numeric"
    else:
        return "text"

def print_comprehensive_metadata():
    """Prints comprehensive metadata to the console."""
    print("\n--- Comprehensive Metadata ---")
    print(f"Total Groups Processed: {metadata['total_groups_processed']}")
    print(f"Total Sections Extracted: {metadata['total_sections_extracted']}")
    print(f"Average Sections per Group: {metadata['splitting_stats']['average_sections_per_group']:.1f}")
    print(f"Max Sections in a Group: {metadata['splitting_stats']['max_sections_in_group']}")
    print("\n--- Section Number Distribution ---")
    for section_num, count in metadata["section_analysis"]["section_number_distribution"].most_common():
        print(f"Section {section_num}: {count} times")
    print("\n--- Version Label Distribution ---")
    for version_label, count in metadata["section_analysis"]["version_label_distribution"].most_common():
        print(f"{version_label}: {count} times")
    print("\n--- Base Statute Distribution ---")
    for base_statute, count in metadata["section_analysis"]["base_statute_distribution"].most_common():
        print(f"{base_statute}: {count} times")
    print("\n--- Sample Sections ---")
    for i, sample in enumerate(metadata["section_analysis"]["sample_sections"], 1):
        print(f"Sample {i}:")
        print(f"  Base Statute: {sample['base_statute_name']}")
        print(f"  Section Number: {sample['section_number']}")
        print(f"  Version Label: {sample['version_label']}")
        print(f"  Definition Length: {sample['definition_length']}")
        print(f"  Text Length: {sample['text_length']}")
        print(f"  Has Citations: {sample['has_citations']}")
        print("-" * 20)
    print("--- End of Metadata ---")

def save_metadata_to_file():
    """Save comprehensive metadata to JSON file with new naming convention"""
    import os
    os.makedirs("metadata", exist_ok=True)
    metadata_filename = f"metadata_section_splitting_{SOURCE_DB}_{SOURCE_COLL}_{date.today().isoformat()}.json"
    metadata_file = f"metadata/{metadata_filename}"
    # Convert Counter objects to regular dictionaries for JSON serialization
    metadata_for_json = {
        "total_groups_processed": metadata["total_groups_processed"],
        "total_sections_extracted": metadata["total_sections_extracted"],
        "splitting_stats": metadata["splitting_stats"],
        "section_analysis": {
            "section_number_distribution": dict(metadata["section_analysis"]["section_number_distribution"]),
            "version_label_distribution": dict(metadata["section_analysis"]["version_label_distribution"]),
            "base_statute_distribution": dict(metadata["section_analysis"]["base_statute_distribution"]),
            "sample_sections": metadata["section_analysis"]["sample_sections"]
        },
        "processing_details": metadata["processing_details"]
    }
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(metadata_for_json, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n📊 Metadata saved to: {metadata_file}")
    return metadata_file

def split_sections_from_database():
    """
    Main function to split sections from versioned grouped statutes
    """
    client = connect_to_mongodb()
    if not client:
        return
    
    try:
        # Get source and target collections
        source_col = client[SOURCE_DB][SOURCE_COLL]
        target_col = client[TARGET_DB][TARGET_COLL]
        
        # Clear target collection
        target_col.delete_many({})
        print(f"🧹 Cleared target collection {TARGET_DB}.{TARGET_COLL}")
        
        # Get all versioned grouped statutes
        grouped_statutes = list(source_col.find({}))
        metadata["total_groups_processed"] = len(grouped_statutes)
        print(f"📄 Found {len(grouped_statutes)} versioned grouped statutes to process")
        
        total_sections = 0
        processed_groups = 0
        total_versions = 0
        
        # Process each versioned grouped statute
        for group_doc in tqdm(grouped_statutes, desc="Processing versioned grouped statutes"):
            try:
                # Extract sections from this group
                sections = process_sections_vectorized(group_doc)
                
                if sections:
                    # Insert sections into target collection
                    result = target_col.insert_many(sections)
                    total_sections += len(sections)
                    processed_groups += 1
                    total_versions += len(group_doc.get("versions", []))
                    
                    print(f"📋 Extracted {len(sections)} sections from {group_doc.get('base_name', 'Unknown')}")
                else:
                    metadata["splitting_stats"]["groups_without_sections"] += 1
                
            except Exception as e:
                print(f"❌ Error processing group {group_doc.get('base_name', 'Unknown')}: {e}")
                continue
        
        # Calculate final statistics
        metadata["total_sections_extracted"] = total_sections
        metadata["splitting_stats"]["groups_with_sections"] = processed_groups
        metadata["splitting_stats"]["total_versions_processed"] = total_versions
        metadata["splitting_stats"]["average_sections_per_group"] = total_sections / processed_groups if processed_groups > 0 else 0
        
        # Find max sections in a group
        max_sections = 0
        for group_doc in grouped_statutes:
            sections_count = sum(len(version.get("sections", [])) for version in group_doc.get("versions", []))
            max_sections = max(max_sections, sections_count)
        metadata["splitting_stats"]["max_sections_in_group"] = max_sections
        
        # Create indexes for better performance
        target_col.create_index([("base_statute_name", 1)])
        target_col.create_index([("section_number", 1)])
        target_col.create_index([("group_id", 1)])
        target_col.create_index([("version_label", 1)])
        
        print(f"✅ Successfully processed {processed_groups} groups")
        print(f"📊 Total sections extracted: {total_sections}")
        print(f"📈 Average sections per group: {metadata['splitting_stats']['average_sections_per_group']:.1f}")
        
        # Print comprehensive metadata
        print_comprehensive_metadata()
        
        # Save metadata to file
        save_metadata_to_file()
        
        # Show some examples
        print("\n📋 Example Sections:")
        sample_sections = list(target_col.find().limit(5))
        for i, section in enumerate(sample_sections, 1):
            print(f"   {i}. {section.get('base_statute_name', 'Unknown')} - Section {section.get('section_number', 'Unknown')}")
            print(f"      Definition: {section.get('definition', 'No definition')}")
            print(f"      Version: {section.get('version_label', 'Unknown')}")
            print(f"      Text length: {len(section.get('statute_text', ''))} characters")
            print("")
        
        # Export summary to JSON
        summary = {
            "total_groups_processed": processed_groups,
            "total_sections_extracted": total_sections,
            "average_sections_per_group": metadata["splitting_stats"]["average_sections_per_group"],
            "processing_date": datetime.now().isoformat(),
            "source_database": SOURCE_DB,
            "target_database": TARGET_DB
        }
        summary_filename = f"sections_split_summary_{SOURCE_DB}_{SOURCE_COLL}_{date.today().isoformat()}.json"
        summary_path = f"06_section_versioning/{summary_filename}"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, default=str)
        print(f"💾 Summary exported to {summary_path}")
        
    except Exception as e:
        print(f"❌ Error in split_sections_from_database: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    print("🚀 Starting Section Splitting Process")
    split_sections_from_database()
    print("✅ Section splitting process completed")
