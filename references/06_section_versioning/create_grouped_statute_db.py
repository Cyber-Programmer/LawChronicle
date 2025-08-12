"""
Create Grouped Statute Database

This script takes section versions and groups them into complete statute documents
in the database, with proper handling of unknown dates and ordinance expiration.

Features:
- Groups sections by base statute name
- Handles unknown/invalid dates gracefully
- Creates complete statute documents with all sections
- Maintains version timelines and active status
- Creates clean database structure for easy querying
- Uses numpy for faster processing operations
"""

import numpy as np
from pymongo import MongoClient
from tqdm import tqdm
import json
from datetime import datetime, timedelta, date
from dateutil import parser
from collections import defaultdict, Counter
from typing import List, Dict, Optional

# --- CONFIG ---
MONGO_URI = "mongodb://localhost:27017"
SOURCE_DB = "Batch-Section-Versioned"  # Updated to match coherent pipeline
SOURCE_COLL = "batch10"
TARGET_DB = "Final-Batched-Statutes"  # Updated naming
TARGET_COLL = "batch10"

# Initialize metadata tracking
metadata = {
    "total_section_versions_processed": 0,
    "total_statutes_grouped": 0,
    "grouping_stats": {
        "statutes_with_sections": 0,
        "statutes_without_sections": 0,
        "max_sections_per_statute": 0,
        "average_sections_per_statute": 0,
        "total_sections_grouped": 0,
        "total_versions_grouped": 0
    },
    "content_analysis": {
        "province_distribution": Counter(),
        "statute_type_distribution": Counter(),
        "active_versions": 0,
        "inactive_versions": 0,
        "expired_ordinances": 0,
        "sample_statutes": []
    },
    "processing_details": {
        "sections_with_valid_dates": 0,
        "sections_with_invalid_dates": 0,
        "sections_with_missing_dates": 0,
        "database_updates": 0
    }
}

def print_comprehensive_metadata():
    """Print comprehensive metadata about the grouping process"""
    print(f"\n📊 COMPREHENSIVE GROUPING METADATA:")
    print("=" * 60)
    print(f"📋 Total section versions processed: {metadata['total_section_versions_processed']}")
    print(f"📋 Total statutes grouped: {metadata['total_statutes_grouped']}")
    
    print(f"\n📊 Grouping Statistics:")
    print(f"   - Statutes with sections: {metadata['grouping_stats']['statutes_with_sections']}")
    print(f"   - Total sections grouped: {metadata['grouping_stats']['total_sections_grouped']}")
    print(f"   - Total versions grouped: {metadata['grouping_stats']['total_versions_grouped']}")
    print(f"   - Average sections per statute: {metadata['grouping_stats']['average_sections_per_statute']:.1f}")
    print(f"   - Max sections per statute: {metadata['grouping_stats']['max_sections_per_statute']}")
    
    print(f"\n📊 Content Analysis:")
    print(f"   - Active versions: {metadata['content_analysis']['active_versions']}")
    print(f"   - Inactive versions: {metadata['content_analysis']['inactive_versions']}")
    print(f"   - Expired ordinances: {metadata['content_analysis']['expired_ordinances']}")
    
    print(f"\n📊 Province Distribution (Top 10):")
    for province, count in metadata["content_analysis"]["province_distribution"].most_common(10):
        print(f"   - {province}: {count} statutes")
    
    print(f"\n📊 Statute Type Distribution:")
    for statute_type, count in metadata["content_analysis"]["statute_type_distribution"].most_common():
        print(f"   - {statute_type}: {count} statutes")
    
    print(f"\n📊 Sample Grouped Statutes:")
    for i, sample in enumerate(metadata["content_analysis"]["sample_statutes"][:5]):
        print(f"   {i+1}. {sample['base_name']}: {sample['section_count']} sections")
        print(f"      Active versions: {sample['active_versions']}, Inactive: {sample['inactive_versions']}")
        print(f"      Province: {sample['province']}, Type: {sample['statute_type']}")

def save_metadata_to_file():
    """Save comprehensive metadata to JSON file with new naming convention"""
    import os
    os.makedirs("metadata", exist_ok=True)
    metadata_filename = f"metadata_grouped_statute_{TARGET_DB}_{TARGET_COLL}_{date.today().isoformat()}.json"
    metadata_file = f"metadata/{metadata_filename}"
    # Convert Counter objects to regular dictionaries for JSON serialization
    metadata_for_json = {
        "total_section_versions_processed": metadata["total_section_versions_processed"],
        "total_statutes_grouped": metadata["total_statutes_grouped"],
        "grouping_stats": metadata["grouping_stats"],
        "content_analysis": {
            "province_distribution": dict(metadata["content_analysis"]["province_distribution"]),
            "statute_type_distribution": dict(metadata["content_analysis"]["statute_type_distribution"]),
            "active_versions": metadata["content_analysis"]["active_versions"],
            "inactive_versions": metadata["content_analysis"]["inactive_versions"],
            "expired_ordinances": metadata["content_analysis"]["expired_ordinances"],
            "sample_statutes": metadata["content_analysis"]["sample_statutes"]
        },
        "processing_details": metadata["processing_details"]
    }
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(metadata_for_json, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n📊 Metadata saved to: {metadata_file}")

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

def parse_date_safely(date_str: str) -> Optional[datetime]:
    """Parse date string safely, handling unknown/invalid dates"""
    if not date_str or date_str.lower() in ['unknown', 'none', 'null', '']:
        return None
    
    try:
        # Try different date formats
        for fmt in ['%d-%b-%Y', '%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y']:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        # Try dateutil parser as fallback
        return parser.parse(date_str)
    except Exception as e:
        print(f"⚠️ Could not parse date '{date_str}': {e}")
        return None

def group_sections_by_base_statute(sections: List[Dict]) -> Dict[str, Dict]:
    """
    Group sections by base statute name using numpy for faster operations.
    Args:
        sections: List of section version documents from database
    Returns:
        Dictionary: {base_statute_name: complete_statute_document}
    """
    if not sections:
        return {}
    
    # Convert to numpy arrays for faster processing
    base_names = np.array([section.get("base_statute_name", "") for section in sections])
    provinces = np.array([section.get("Province", section.get("province", "")) for section in sections])
    statute_types = np.array([section.get("Statute_Type", section.get("statute_type", "")) for section in sections])
    
    # Group sections using numpy operations
    unique_base_names = np.unique(base_names)
    grouped_statutes = {}
    
    for base_name in unique_base_names:
        if not base_name:
            continue
            
        # Find sections for this base name
        mask = np.char.equal(base_names, base_name)
        base_sections = [sections[i] for i in np.where(mask)[0]]
        
        if base_sections:
            # Initialize statute document
            first_section = base_sections[0]
            grouped_statutes[base_name] = {
                "base_statute_name": base_name,
                "Province": first_section.get("Province", first_section.get("province", "")),
                "Statute_Type": first_section.get("Statute_Type", first_section.get("statute_type", "")),
                "Section_Versions": [],
                "total_sections": 0,
                "total_versions": 0,
                "latest_version_date": None,
                "processing_date": datetime.now().isoformat()
            }
            
            # Process sections using vectorized operations where possible
            for section in base_sections:
                # Harmonize field names and ensure Versions is present and non-empty
                versions = section.get("Versions", []) or section.get("versions", [])
                if not versions:
                    print(f"⚠️ Section {section.get('section_number', section.get('Section', ''))} in {base_name} has empty Versions array.")
                    continue
                    
                section_version = {
                    "Section": section.get("section_number", section.get("Section", "")),
                    "Definition": section.get("definition", section.get("Definition", "")),
                    "Versions": versions
                }
                
                # Process versions using numpy for date operations
                version_dates = np.array([version.get("Promulgation_Date", "") for version in versions])
                parsed_dates = np.array([parse_date_safely(date_str) for date_str in version_dates])
                
                # Find latest date using numpy operations
                valid_dates = parsed_dates[parsed_dates != None]
                if valid_dates.size > 0:
                    latest_date = np.max(valid_dates)
                    if (grouped_statutes[base_name]["latest_version_date"] is None or
                        latest_date > grouped_statutes[base_name]["latest_version_date"]):
                        grouped_statutes[base_name]["latest_version_date"] = latest_date
                
                grouped_statutes[base_name]["total_versions"] += len(versions)
                grouped_statutes[base_name]["Section_Versions"].append(section_version)
                grouped_statutes[base_name]["total_sections"] += 1
    
    # Convert latest_version_date to isoformat using numpy operations
    for statute in grouped_statutes.values():
        if statute["latest_version_date"]:
            statute["latest_version_date"] = statute["latest_version_date"].isoformat()
    
    return grouped_statutes

def create_grouped_statute_database():
    """
    Main function to create grouped statute database
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
        
        # Get all section versions
        all_sections = list(source_col.find({}))
        metadata["total_section_versions_processed"] = len(all_sections)
        print(f"📄 Found {len(all_sections)} section versions to group")
        
        # Group sections by base statute
        grouped_statutes = group_sections_by_base_statute(all_sections)
        metadata["total_statutes_grouped"] = len(grouped_statutes)
        print(f"📊 Grouped into {len(grouped_statutes)} statutes")
        
        # Calculate statistics and track metadata
        total_sections = 0
        total_versions = 0
        max_sections = 0
        
        for base_name, statute_doc in grouped_statutes.items():
            section_count = statute_doc.get("total_sections", 0)
            version_count = statute_doc.get("total_versions", 0)
            province = statute_doc.get("Province", "")
            statute_type = statute_doc.get("Statute_Type", "")
            
            # Track statistics
            total_sections += section_count
            total_versions += version_count
            max_sections = max(max_sections, section_count)
            
            # Track content analysis
            metadata["content_analysis"]["province_distribution"][province] += 1
            metadata["content_analysis"]["statute_type_distribution"][statute_type] += 1
            
            # Track active/inactive versions
            active_count = 0
            inactive_count = 0
            expired_count = 0
            
            for section in statute_doc.get("Section_Versions", []):
                for version in section.get("Versions", []):
                    if version.get("isActive", False):
                        active_count += 1
                    else:
                        inactive_count += 1
                    
                    if version.get("is_expired", False):
                        expired_count += 1
            
            metadata["content_analysis"]["active_versions"] += active_count
            metadata["content_analysis"]["inactive_versions"] += inactive_count
            metadata["content_analysis"]["expired_ordinances"] += expired_count
            
            # Store sample statute
            if len(metadata["content_analysis"]["sample_statutes"]) < 10:
                sample_statute = {
                    "base_name": base_name,
                    "section_count": section_count,
                    "active_versions": active_count,
                    "inactive_versions": inactive_count,
                    "province": province,
                    "statute_type": statute_type
                }
                metadata["content_analysis"]["sample_statutes"].append(sample_statute)
        
        # Update final statistics
        metadata["grouping_stats"]["statutes_with_sections"] = len(grouped_statutes)
        metadata["grouping_stats"]["total_sections_grouped"] = total_sections
        metadata["grouping_stats"]["total_versions_grouped"] = total_versions
        metadata["grouping_stats"]["max_sections_per_statute"] = max_sections
        metadata["grouping_stats"]["average_sections_per_statute"] = total_sections / len(grouped_statutes) if grouped_statutes else 0
        
        # Insert grouped statutes into database
        statute_documents = list(grouped_statutes.values())
        result = target_col.insert_many(statute_documents)
        metadata["processing_details"]["database_updates"] = len(statute_documents)
        
        # Create indexes for better performance
        target_col.create_index([("base_statute_name", 1)])
        target_col.create_index([("Province", 1)])
        target_col.create_index([("Statute_Type", 1)])
        target_col.create_index([("latest_version_date", 1)])
        
        print(f"✅ Successfully created {len(statute_documents)} grouped statute documents")
        
        # Print comprehensive metadata
        print_comprehensive_metadata()
        
        # Save metadata to file
        save_metadata_to_file()
        
        # Show statistics
        avg_sections = metadata["grouping_stats"]["average_sections_per_statute"]
        
        print(f"📊 Total sections: {total_sections}")
        print(f"📊 Total versions: {total_versions}")
        print(f"📈 Average sections per statute: {avg_sections:.1f}")
        
        # Show some examples
        print("\n📋 Example Grouped Statutes:")
        sample_statutes = list(target_col.find().limit(3))
        for i, statute in enumerate(sample_statutes, 1):
            print(f"   {i}. {statute.get('base_statute_name', 'Unknown')}")
            print(f"      Province: {statute.get('Province', 'Unknown')}")
            print(f"      Type: {statute.get('Statute_Type', 'Unknown')}")
            print(f"      Sections: {statute.get('total_sections', 0)}")
            print(f"      Versions: {statute.get('total_versions', 0)}")
            print("")
        
        # Export summary to JSON
        # The summary file is defined here:
        summary = {
            "total_statutes_grouped": len(statute_documents),
            "total_sections": total_sections,
            "total_versions": total_versions,
            "average_sections_per_statute": avg_sections,
            "processing_date": datetime.now().isoformat(),
            "source_database": SOURCE_DB,
            "target_database": TARGET_DB
        }
        summary_filename = f"grouped_statutes_summary_{TARGET_DB}_{TARGET_COLL}_{date.today().isoformat()}.json"
        summary_path = f"06_section_versioning/{summary_filename}"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, default=str)
        print(f"💾 Summary exported to {summary_path}")
        
    except Exception as e:
        print(f"❌ Error in Final-Batched-Statutes_database: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    print("🚀 Starting Grouped Statute Database Creation")
    create_grouped_statute_database()
    print("✅ Grouped statute database creation completed") 