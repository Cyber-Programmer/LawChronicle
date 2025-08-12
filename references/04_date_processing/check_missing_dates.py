"""
Check Missing Dates in Filled Database Collections

This script checks the newly created filled database collections and identifies
statutes that still have missing dates. It provides a comprehensive report
of remaining missing dates for further processing.

Features:
- Connects to filled database collections
- Identifies statutes with missing dates
- Provides detailed statistics and analysis
- Exports missing dates to CSV for review
- Generates summary report
"""

import numpy as np
from pymongo import MongoClient
from tqdm import tqdm
import json
import argparse
import os
from datetime import datetime
from collections import defaultdict, Counter
from typing import List, Dict, Optional, Tuple


# Simple print logging
def log_info(message):
    print(f"INFO: {message}")

def log_error(message):
    print(f"ERROR: {message}")

def log_warning(message):
    print(f"WARNING: {message}")

# --- CONFIG ---
MONGO_URI = "mongodb://localhost:27017"
SOURCE_DB = "Batch-Base-Grouped-Filled"  # Check the filled database
SOURCE_COLL = "batch2"  # Change this to your specific batch

# Initialize metadata tracking
metadata = {
    "script": "check_missing_dates.py",
    "execution_date": datetime.now().isoformat(),
    "source_database": f"{SOURCE_DB}.{SOURCE_COLL}",
    "missing_dates_analysis": {
        "total_groups_checked": 0,
        "total_statutes_checked": 0,
        "statutes_with_dates": 0,
        "statutes_with_missing_dates": 0,
        "missing_dates_percentage": 0.0,
        "groups_with_missing_dates": 0,
        "groups_with_all_dates": 0
    },
    "group_analysis": {
        "groups_by_missing_count": Counter(),
        "sample_groups_with_missing": [],
        "sample_groups_with_all_dates": []
    },
    "statute_analysis": {
        "missing_statutes_by_province": Counter(),
        "missing_statutes_by_type": Counter(),
        "missing_statutes_by_base_name": Counter(),
        "sample_missing_statutes": []
    },
    "error_log": {
        "database_errors": [],
        "processing_errors": []
    }
}

def connect_to_mongodb():
    """Connect to MongoDB and return client"""
    try:
        client = MongoClient(MONGO_URI)
        client.admin.command('ping')
        log_info("Connected to MongoDB successfully")
        return client
    except Exception as e:
        log_error(f"Failed to connect to MongoDB: {e}")
        return None

def get_grouped_statutes_with_dates_status(client: MongoClient) -> Tuple[List[Dict], List[Dict], Dict]:
    """
    Get all grouped statutes from filled collection and analyze date status
    
    Returns:
    - groups: List of all groups
    - missing_statutes: List of statutes with missing dates
    - stats: Dictionary with statistics
    """
    try:
        source_col = client[SOURCE_DB][SOURCE_COLL]
        groups = list(source_col.find({}))
        
        total_statutes = 0
        statutes_with_dates = 0
        statutes_with_missing_dates = 0
        missing_statutes = []
        
        # Analyze each group
        for group in groups:
            statutes = group.get("statutes", [])
            total_statutes += len(statutes)
            
            group_missing_count = 0
            for statute in statutes:
                date_field = statute.get("Date", "")
                if not date_field or str(date_field).strip() == "":
                    statutes_with_missing_dates += 1
                    group_missing_count += 1
                    
                    # Add group context to missing statute
                    missing_statute = {
                        **statute,
                        "_group_id": group["_id"],
                        "_group_base_name": group.get("base_name", ""),
                        "_group_province": group.get("province", ""),
                        "_group_statute_type": group.get("statute_type", "")
                    }
                    missing_statutes.append(missing_statute)
                else:
                    statutes_with_dates += 1
            
            # Track group statistics
            metadata["group_analysis"]["groups_by_missing_count"][group_missing_count] += 1
            
            # Add sample groups
            if group_missing_count > 0:
                if len(metadata["group_analysis"]["sample_groups_with_missing"]) < 5:
                    metadata["group_analysis"]["sample_groups_with_missing"].append({
                        "group_id": str(group["_id"]),
                        "base_name": group.get("base_name", ""),
                        "province": group.get("province", ""),
                        "statute_type": group.get("statute_type", ""),
                        "total_statutes": len(statutes),
                        "missing_dates": group_missing_count
                    })
            else:
                if len(metadata["group_analysis"]["sample_groups_with_all_dates"]) < 5:
                    metadata["group_analysis"]["sample_groups_with_all_dates"].append({
                        "group_id": str(group["_id"]),
                        "base_name": group.get("base_name", ""),
                        "province": group.get("province", ""),
                        "statute_type": group.get("statute_type", ""),
                        "total_statutes": len(statutes)
                    })
        
        # Calculate statistics
        stats = {
            "total_groups": len(groups),
            "total_statutes": total_statutes,
            "statutes_with_dates": statutes_with_dates,
            "statutes_with_missing_dates": statutes_with_missing_dates,
            "missing_dates_percentage": (statutes_with_missing_dates / total_statutes * 100) if total_statutes > 0 else 0,
            "groups_with_missing_dates": sum(1 for count in metadata["group_analysis"]["groups_by_missing_count"].items() if count[0] > 0),
            "groups_with_all_dates": metadata["group_analysis"]["groups_by_missing_count"][0]
        }
        
        log_info(f"Found {len(groups)} groups with {total_statutes} total statutes")
        log_info(f"Statutes with dates: {statutes_with_dates}, Missing dates: {statutes_with_missing_dates} ({stats['missing_dates_percentage']:.1f}%)")
        
        return groups, missing_statutes, stats
        
    except Exception as e:
        log_error(f"Error fetching grouped statutes: {e}")
        metadata["error_log"]["database_errors"].append(str(e))
        raise

def analyze_missing_statutes(missing_statutes: List[Dict]):
    """Analyze missing statutes by various categories"""
    try:
        # Analyze by province
        for statute in missing_statutes:
            province = statute.get("_group_province", "Unknown")
            statute_type = statute.get("_group_statute_type", "Unknown")
            base_name = statute.get("_group_base_name", "Unknown")
            
            metadata["statute_analysis"]["missing_statutes_by_province"][province] += 1
            metadata["statute_analysis"]["missing_statutes_by_type"][statute_type] += 1
            metadata["statute_analysis"]["missing_statutes_by_base_name"][base_name] += 1
        
        # Add sample missing statutes
        metadata["statute_analysis"]["sample_missing_statutes"] = [
            {
                "statute_name": statute.get("Statute_Name", ""),
                "province": statute.get("_group_province", ""),
                "statute_type": statute.get("_group_statute_type", ""),
                "base_name": statute.get("_group_base_name", "")
            }
            for statute in missing_statutes[:10]  # First 10
        ]
        
        log_info(f"Missing dates analysis completed")
        
    except Exception as e:
        log_error(f"Error analyzing missing statutes: {e}")
        metadata["error_log"]["processing_errors"].append(str(e))

def save_missing_statutes_to_csv(missing_statutes: List[Dict], output_dir: str = "exports"):
    """Save missing statutes to CSV file for review"""
    try:
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        if not missing_statutes:
            log_info("No missing statutes to export")
            return None
        
        timestamp = datetime.now().strftime("%Y-%m-%d")
        filename = f"missing_dates_statutes_{SOURCE_DB}_{SOURCE_COLL}_{timestamp}.csv"
        filepath = os.path.join(output_dir, filename)
        
        import csv
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            # Define fieldnames
            fieldnames = [
                "Statute_Name", "Date", "Province", "Statute_Type", "Base_Name",
                "Group_ID", "File_ID", "Bookmark_ID"
            ]
            
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for statute in missing_statutes:
                row = {
                    "Statute_Name": statute.get("Statute_Name", ""),
                    "Date": statute.get("Date", ""),
                    "Province": statute.get("_group_province", ""),
                    "Statute_Type": statute.get("_group_statute_type", ""),
                    "Base_Name": statute.get("_group_base_name", ""),
                    "Group_ID": str(statute.get("_group_id", "")),
                    "File_ID": statute.get("File_ID", ""),
                    "Bookmark_ID": statute.get("Bookmark_ID", "")
                }
                writer.writerow(row)
        
        log_info(f"Missing statutes exported to: {filepath}")
        return filepath
        
    except Exception as e:
        log_error(f"Error saving missing statutes to CSV: {e}")
        return None

def save_metadata_to_file(metadata: Dict, output_dir: str = "metadata"):
    """Save metadata to JSON file"""
    try:
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        timestamp = datetime.now().strftime("%Y-%m-%d")
        filename = f"check_missing_dates_metadata_{SOURCE_DB}_{SOURCE_COLL}_{timestamp}.json"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False, default=str)
        
        log_info(f"Metadata saved to: {filepath}")
        return filepath
        
    except Exception as e:
        log_error(f"Error saving metadata: {e}")
        raise

def print_summary(metadata: Dict, stats: Dict, missing_statutes: List[Dict]):
    """Print comprehensive summary"""
    print("\n" + "="*70)
    print("📊 CHECK MISSING DATES - COMPREHENSIVE SUMMARY")
    print("="*70)
    
    print(f"📄 Database: {metadata['source_database']}")
    print(f"📅 Check Date: {metadata['execution_date']}")
    
    print(f"\n📊 OVERALL STATISTICS:")
    print(f"   Total Groups: {stats['total_groups']}")
    print(f"   Total Statutes: {stats['total_statutes']}")
    print(f"   Statutes with Dates: {stats['statutes_with_dates']}")
    print(f"   Statutes Missing Dates: {stats['statutes_with_missing_dates']}")
    print(f"   Missing Dates Percentage: {stats['missing_dates_percentage']:.1f}%")
    
    print(f"\n🏛️ GROUP ANALYSIS:")
    print(f"   Groups with Missing Dates: {stats['groups_with_missing_dates']}")
    print(f"   Groups with All Dates: {stats['groups_with_all_dates']}")
    
    # Show missing counts distribution
    missing_dist = metadata["group_analysis"]["groups_by_missing_count"]
    if missing_dist:
        print(f"\n📈 Missing Dates Distribution:")
        for missing_count, group_count in sorted(missing_dist.items()):
            if missing_count == 0:
                print(f"   {missing_count} missing: {group_count} groups (complete)")
            else:
                print(f"   {missing_count} missing: {group_count} groups")
    
    # Show top provinces with missing dates
    province_stats = metadata["statute_analysis"]["missing_statutes_by_province"]
    if province_stats:
        print(f"\n🏛️ Missing Dates by Province:")
        for province, count in province_stats.most_common(5):
            print(f"   {province}: {count} statutes")
    
    # Show top statute types with missing dates
    type_stats = metadata["statute_analysis"]["missing_statutes_by_type"]
    if type_stats:
        print(f"\n📜 Missing Dates by Statute Type:")
        for statute_type, count in type_stats.most_common(5):
            print(f"   {statute_type}: {count} statutes")
    
    # Show sample missing statutes
    if missing_statutes:
        print(f"\n📋 Sample Missing Statutes (first 5):")
        for i, statute in enumerate(missing_statutes[:5], 1):
            print(f"   {i}. {statute.get('Statute_Name', 'Unknown')}")
            print(f"      Province: {statute.get('_group_province', 'Unknown')}")
            print(f"      Type: {statute.get('_group_statute_type', 'Unknown')}")
    
    print("="*70)

def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description="Check missing dates in filled database collections")
    parser.add_argument("--source-db", default=SOURCE_DB, help="Source database name")
    parser.add_argument("--source-coll", default=SOURCE_COLL, help="Source collection name")
    parser.add_argument("--output-dir", default="metadata", help="Output directory for metadata")
    parser.add_argument("--exports-dir", default="exports", help="Output directory for exports")
    
    args = parser.parse_args()
    
    # Update config
    global SOURCE_DB, SOURCE_COLL
    SOURCE_DB = args.source_db
    SOURCE_COLL = args.source_coll
    
    # Update metadata
    metadata["source_database"] = f"{SOURCE_DB}.{SOURCE_COLL}"
    
    try:
        log_info("Starting Check Missing Dates process")
        
        # Connect to MongoDB
        client = connect_to_mongodb()
        if not client:
            return
        
        # Get grouped statutes and analyze missing dates
        groups, missing_statutes, stats = get_grouped_statutes_with_dates_status(client)
        
        # Update metadata
        metadata["missing_dates_analysis"].update(stats)
        
        # Analyze missing statutes
        analyze_missing_statutes(missing_statutes)
        
        # Save exports
        csv_file = save_missing_statutes_to_csv(missing_statutes, args.exports_dir)
        metadata_file = save_metadata_to_file(metadata, args.output_dir)
        
        # Print summary
        print_summary(metadata, stats, missing_statutes)
        
        log_info("Check Missing Dates process completed successfully")
        
        if missing_statutes:
            log_warning(f"Found {len(missing_statutes)} statutes still missing dates")
        else:
            log_info("✅ All statutes have dates!")
        
    except Exception as e:
        log_error(f"Process failed: {e}")
        metadata["error_log"]["processing_errors"] = str(e)
        save_metadata_to_file(metadata, args.output_dir)
        raise
    finally:
        if 'client' in locals():
            client.close()

if __name__ == "__main__":
    main() 