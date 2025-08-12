"""
Fill Missing Dates in Grouped Batch Databases

This script takes an Excel file containing statute identifiers and their missing dates,
then updates the MongoDB grouped batch collection by filling in the missing dates 
for statutes within the grouped structure. It also generates comprehensive metadata.

Features:
- Loads date mappings from Excel file
- Updates missing dates in grouped batch MongoDB collection
- Handles nested statute structure within groups
- Generates comprehensive metadata summary
- Provides detailed logging and error handling
- Exports unmatched statutes for review
"""

import numpy as np
import openpyxl
from pymongo import MongoClient
from tqdm import tqdm
import json
import argparse
import os
from datetime import datetime, date
from collections import defaultdict, Counter
from typing import List, Dict, Optional, Tuple


# Simple print logging instead of file logging
def log_info(message):
    print(f"INFO: {message}")

def log_error(message):
    print(f"ERROR: {message}")

def log_warning(message):
    print(f"WARNING: {message}")

# --- CONFIG ---
MONGO_URI = "mongodb://localhost:27017"
SOURCE_DB = "Batch-Base-Grouped"
SOURCE_COLL = "batch10"  # Change this to your specific batch
# TODAY_STR stores today's date as a string in "YYYY-MM-DD" format for use in filenames, logs, or metadata.
TODAY_STR = datetime.now().strftime("%Y-%m-%d")
TARGET_DB = f"{SOURCE_DB}-Filled"
TARGET_COLL = f"{SOURCE_COLL}"

# Initialize metadata tracking
metadata = {
    "script": "fill_dates_grouped_batches.py",
    "execution_date": datetime.now().isoformat(),
    "source_database": f"{SOURCE_DB}.{SOURCE_COLL}",
    "target_database": f"{TARGET_DB}.{TARGET_COLL}",
    "processing_stats": {
        "total_groups_processed": 0,
        "total_statutes_processed": 0,
        "statutes_with_missing_dates_before": 0,
        "statutes_with_missing_dates_after": 0,
        "dates_filled_from_excel": 0,
        "statutes_unchanged": 0,
        "statutes_updated": 0
    },
    "excel_analysis": {
        "total_excel_rows": 0,
        "valid_excel_rows": 0,
        "invalid_excel_rows": 0,
        "excel_date_format_issues": 0,
        "sample_excel_dates": []
    },
    "matching_analysis": {
        "exact_matches": 0,
        "fuzzy_matches": 0,
        "unmatched_excel_statutes": 0,
        "unmatched_db_statutes": 0,
        "matching_errors": 0
    },
    "date_analysis": {
        "date_formats_found": Counter(),
        "date_range": {"earliest": None, "latest": None},
        "invalid_dates_found": 0,
        "sample_dates_filled": []
    },
    "error_log": {
        "excel_parsing_errors": [],
        "matching_errors": [],
        "database_errors": []
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

def load_excel_data(excel_file_path: str) -> List[Dict]:
    """
    Load and validate Excel data containing statute-date mappings
    
    Expected columns: Statute_Name, Best_Date, DL_Dates_Extracted, Reason_Selected, File_ID
    """
    try:
        log_info(f"Loading Excel file: {excel_file_path}")
        
        # Load Excel file using openpyxl
        workbook = openpyxl.load_workbook(excel_file_path, data_only=True)
        worksheet = workbook.active
        
        # Get headers from first row
        headers = [cell.value for cell in worksheet[1]]
        
        # Validate required columns
        required_columns = ["Statute_Name", "Best_Date"]
        missing_columns = [col for col in required_columns if col not in headers]
        
        if missing_columns:
            log_error(f"Missing required columns: {missing_columns}")
            log_info(f"Available columns: {headers}")
            raise ValueError(f"Excel file must contain columns: {required_columns}")
        
        # Get column indices
        statute_name_idx = headers.index("Statute_Name")
        date_idx = headers.index("Best_Date")
        
        # Optional columns
        dl_dates_idx = headers.index("DL_Dates_Extracted") if "DL_Dates_Extracted" in headers else None
        reason_idx = headers.index("Reason_Selected") if "Reason_Selected" in headers else None
        file_id_idx = headers.index("File_ID") if "File_ID" in headers else None
        
        # Extract data rows
        data_rows = []
        for row in worksheet.iter_rows(min_row=2):
            statute_name = row[statute_name_idx].value
            date_val = row[date_idx].value
            
            if statute_name is not None and str(statute_name).strip():
                row_data = {
                    "Statute_Name": str(statute_name).strip(),
                    "Best_Date": date_val
                }
                
                # Add optional columns if available
                if dl_dates_idx is not None:
                    row_data["DL_Dates_Extracted"] = row[dl_dates_idx].value
                if reason_idx is not None:
                    row_data["Reason_Selected"] = row[reason_idx].value
                if file_id_idx is not None:
                    row_data["File_ID"] = row[file_id_idx].value
                
                data_rows.append(row_data)
        
        metadata["excel_analysis"]["total_excel_rows"] = len(data_rows)
        
        # Validate dates
        valid_dates = []
        invalid_dates = []
        
        for idx, row in enumerate(data_rows):
            date_val = row["Best_Date"]
            if date_val is None or str(date_val).strip() == "":
                invalid_dates.append((idx, date_val, "Empty date"))
                continue
                
            try:
                # Try to parse the date
                if isinstance(date_val, str):
                    # Handle various date formats
                    date_str = str(date_val).strip()
                    if "/" in date_str:
                        # Handle DD/MM/YYYY or MM/DD/YYYY
                        parts = date_str.split("/")
                        if len(parts) == 3:
                            if len(parts[2]) == 4:  # YYYY format
                                if len(parts[0]) == 2:  # DD format
                                    date_str = f"{parts[2]}-{parts[1]}-{parts[0]}"
                                else:  # MM format
                                    date_str = f"{parts[2]}-{parts[0]}-{parts[1]}"
                    elif "-" in date_str:
                        # Handle DD-MM-YYYY or YYYY-MM-DD
                        parts = date_str.split("-")
                        if len(parts) == 3:
                            if len(parts[0]) == 4:  # YYYY-MM-DD
                                pass  # Already in correct format
                            else:  # DD-MM-YYYY
                                date_str = f"{parts[2]}-{parts[1]}-{parts[0]}"
                    
                    # Use datetime parsing
                    from dateutil import parser
                    parsed_date = parser.parse(date_str, fuzzy=True)
                    valid_dates.append((idx, parsed_date.strftime("%Y-%m-%d")))
                    metadata["date_analysis"]["sample_dates_filled"].append(parsed_date.strftime("%Y-%m-%d"))
                else:
                    # Handle datetime objects
                    from dateutil import parser
                    parsed_date = parser.parse(str(date_val), fuzzy=True)
                    valid_dates.append((idx, parsed_date.strftime("%Y-%m-%d")))
                    metadata["date_analysis"]["sample_dates_filled"].append(parsed_date.strftime("%Y-%m-%d"))
                    
            except Exception as e:
                invalid_dates.append((idx, date_val, f"Parsing error: {str(e)}"))
        
        # Update metadata
        metadata["excel_analysis"]["valid_excel_rows"] = len(valid_dates)
        metadata["excel_analysis"]["invalid_excel_rows"] = len(invalid_dates)
        metadata["excel_analysis"]["excel_date_format_issues"] = len(invalid_dates)
        
        # Log issues
        if invalid_dates:
            log_warning(f"Found {len(invalid_dates)} invalid dates in Excel:")
            for idx, date_val, reason in invalid_dates[:5]:  # Show first 5
                log_warning(f"  Row {idx}: '{date_val}' - {reason}")
        
        # Create clean data with valid dates
        clean_data = []
        for idx, date_str in valid_dates:
            clean_data.append({
                "Statute_Name": data_rows[idx]["Statute_Name"],
                "Date": date_str
            })
        
        log_info(f"Loaded {len(clean_data)} valid statute-date mappings from Excel")
        
        return clean_data
        
    except Exception as e:
        log_error(f"Error loading Excel file: {e}")
        metadata["error_log"]["excel_parsing_errors"].append(str(e))
        raise

def get_grouped_statutes_with_missing_dates(client: MongoClient) -> Tuple[List[Dict], int]:
    """Get all grouped statutes from source collection and count missing dates"""
    try:
        source_col = client[SOURCE_DB][SOURCE_COLL]
        groups = list(source_col.find({}))
        
        total_statutes = 0
        missing_dates_count = 0
        
        # Flatten statutes from all groups for processing
        all_statutes = []
        for group in groups:
            statutes = group.get("statutes", [])
            total_statutes += len(statutes)
            
            for statute in statutes:
                date_field = statute.get("Date", "")
                if not date_field or str(date_field).strip() == "":
                    missing_dates_count += 1
                
                # Add group context to statute for later processing
                statute_with_group = {
                    **statute,
                    "_group_id": group["_id"],
                    "_group_base_name": group.get("base_name", ""),
                    "_group_province": group.get("province", ""),
                    "_group_statute_type": group.get("statute_type", "")
                }
                all_statutes.append(statute_with_group)
        
        log_info(f"Found {len(groups)} groups with {total_statutes} total statutes, {missing_dates_count} with missing dates")
        return groups, all_statutes, missing_dates_count
        
    except Exception as e:
        log_error(f"Error fetching grouped statutes: {e}")
        metadata["error_log"]["database_errors"].append(str(e))
        raise

def match_statutes_to_excel(statutes: List[Dict], excel_data: List[Dict]) -> Tuple[Dict, List, List]:
    """
    Match statutes to Excel data and return mappings and unmatched items
    
    Returns:
    - matched_statutes: Dict mapping statute_id to excel_date
    - unmatched_excel: List of Excel rows not found in DB
    - unmatched_db: List of DB statutes not found in Excel
    """
    matched_statutes = {}
    unmatched_excel = []
    unmatched_db = []
    
    # Create lookup dictionaries
    excel_names = np.array([row["Statute_Name"].strip().lower() for row in excel_data])
    excel_dates = np.array([row["Date"] for row in excel_data])
    
    db_names = np.array([statute.get("Statute_Name", "").strip().lower() for statute in statutes])
    db_ids = np.array([statute["_id"] for statute in statutes])
    
    # Create lookup dictionaries
    excel_lookup = dict(zip(excel_names, excel_dates))
    db_lookup = dict(zip(db_names, db_ids))
    
    # Find matches
    for statute_name, excel_date in excel_lookup.items():
        if statute_name in db_lookup:
            statute_id = db_lookup[statute_name]
            matched_statutes[statute_id] = excel_date
            metadata["matching_analysis"]["exact_matches"] += 1
        else:
            unmatched_excel.append({"Statute_Name": statute_name, "Best_Date": excel_date})
            metadata["matching_analysis"]["unmatched_excel_statutes"] += 1
    
    # Find unmatched DB statutes
    for statute in statutes:
        statute_name = statute.get("Statute_Name", "").strip().lower()
        if statute_name and statute_name not in excel_lookup:
            unmatched_db.append({
                "_id": statute["_id"],
                "Statute_Name": statute.get("Statute_Name", ""),
                "Date": statute.get("Date", ""),
                "Group_Base_Name": statute.get("_group_base_name", ""),
                "Group_Province": statute.get("_group_province", "")
            })
            metadata["matching_analysis"]["unmatched_db_statutes"] += 1
    
    log_info(f"Matched {len(matched_statutes)} statutes, {len(unmatched_excel)} unmatched Excel, {len(unmatched_db)} unmatched DB")
    return matched_statutes, unmatched_excel, unmatched_db

def update_grouped_statutes_with_dates(groups: List[Dict], matched_statutes: Dict) -> List[Dict]:
    """Update grouped statutes with dates from Excel and return updated groups"""
    updated_groups = []
    dates_filled = 0
    
    for group in tqdm(groups, desc="Updating grouped statutes with dates"):
        updated_group = group.copy()
        updated_statutes = []
        
        for statute in group.get("statutes", []):
            statute_id = statute["_id"]
            updated_statute = statute.copy()
            
            if statute_id in matched_statutes:
                # Update with date from Excel
                updated_statute["Date"] = matched_statutes[statute_id]
                dates_filled += 1
                metadata["processing_stats"]["dates_filled_from_excel"] += 1
            else:
                # Keep original date (or empty)
                metadata["processing_stats"]["statutes_unchanged"] += 1
            
            # Remove group context fields
            updated_statute.pop("_group_id", None)
            updated_statute.pop("_group_base_name", None)
            updated_statute.pop("_group_province", None)
            updated_statute.pop("_group_statute_type", None)
            
            updated_statutes.append(updated_statute)
        
        updated_group["statutes"] = updated_statutes
        updated_groups.append(updated_group)
    
    log_info(f"Updated {dates_filled} statutes with dates from Excel")
    return updated_groups

def save_to_new_collection(client: MongoClient, updated_groups: List[Dict]):
    """Save updated grouped statutes to new collection"""
    try:
        target_col = client[TARGET_DB][TARGET_COLL]
        
        # Clear existing collection
        target_col.drop()
        log_info(f"Cleared existing collection: {TARGET_DB}.{TARGET_COLL}")
        
        # Insert updated groups
        if updated_groups:
            target_col.insert_many(updated_groups)
            log_info(f"Saved {len(updated_groups)} groups to {TARGET_DB}.{TARGET_COLL}")
        else:
            log_warning("No groups to save")
            
    except Exception as e:
        log_error(f"Error saving to new collection: {e}")
        metadata["error_log"]["database_errors"].append(str(e))
        raise

def generate_metadata_summary(groups: List[Dict], statutes: List[Dict], excel_data: List[Dict], 
                            matched_statutes: Dict, unmatched_excel: List, unmatched_db: List):
    """Generate comprehensive metadata summary"""
    
    # Update processing stats
    metadata["processing_stats"]["total_groups_processed"] = len(groups)
    metadata["processing_stats"]["total_statutes_processed"] = len(statutes)
    metadata["processing_stats"]["statutes_updated"] = len(matched_statutes)
    
    # Count missing dates after processing
    missing_dates_after = 0
    for statute in statutes:
        date_field = statute.get("Date", "")
        if not date_field or str(date_field).strip() == "":
            missing_dates_after += 1
    
    metadata["processing_stats"]["statutes_with_missing_dates_after"] = missing_dates_after
    
    # Analyze date formats and ranges
    filled_dates = []
    for statute_id, date_str in matched_statutes.items():
        filled_dates.append(date_str)
        metadata["date_analysis"]["date_formats_found"][len(date_str)] += 1
    
    if filled_dates:
        try:
            parsed_dates = [datetime.strptime(d, "%Y-%m-%d") for d in filled_dates]
            metadata["date_analysis"]["date_range"]["earliest"] = min(parsed_dates).strftime("%Y-%m-%d")
            metadata["date_analysis"]["date_range"]["latest"] = max(parsed_dates).strftime("%Y-%m-%d")
        except Exception as e:
            log_warning(f"Error parsing date range: {e}")
    
    # Add sample unmatched items
    metadata["matching_analysis"]["sample_unmatched_excel"] = unmatched_excel[:10]
    metadata["matching_analysis"]["sample_unmatched_db"] = unmatched_db[:10]

def save_metadata_to_file(metadata: Dict, output_dir: str = "metadata"):
    """Save metadata to JSON file"""
    try:
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        timestamp = datetime.now().strftime("%Y-%m-%d")
        filename = f"fill_dates_grouped_batches_metadata_{SOURCE_DB}_{SOURCE_COLL}_{timestamp}.json"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False, default=str)
        
        log_info(f"Metadata saved to: {filepath}")
        return filepath
        
    except Exception as e:
        log_error(f"Error saving metadata: {e}")
        raise

def save_unmatched_statutes(unmatched_excel: List, unmatched_db: List, output_dir: str = "exports"):
    """Save unmatched statutes to CSV files for review"""
    try:
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        timestamp = datetime.now().strftime("%Y-%m-%d")
        
        # Save unmatched Excel statutes
        if unmatched_excel:
            import csv
            excel_file = os.path.join(output_dir, f"unmatched_excel_statutes_{SOURCE_DB}_{SOURCE_COLL}_{timestamp}.csv")
            with open(excel_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=unmatched_excel[0].keys())
                writer.writeheader()
                writer.writerows(unmatched_excel)
            log_info(f"Unmatched Excel statutes saved to: {excel_file}")
        
        # Save unmatched DB statutes
        if unmatched_db:
            import csv
            db_file = os.path.join(output_dir, f"unmatched_db_statutes_{SOURCE_DB}_{SOURCE_COLL}_{timestamp}.csv")
            with open(db_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=unmatched_db[0].keys())
                writer.writeheader()
                writer.writerows(unmatched_db)
            log_info(f"Unmatched DB statutes saved to: {db_file}")
            
    except Exception as e:
        log_error(f"Error saving unmatched statutes: {e}")

def print_summary(metadata: Dict):
    """Print processing summary"""
    print("\n" + "="*60)
    print("📊 FILL DATES GROUPED BATCHES - PROCESSING SUMMARY")
    print("="*60)
    
    stats = metadata["processing_stats"]
    print(f"📄 Total groups processed: {stats['total_groups_processed']}")
    print(f"📄 Total statutes processed: {stats['total_statutes_processed']}")
    print(f"📅 Statutes with missing dates (before): {stats['statutes_with_missing_dates_before']}")
    print(f"📅 Statutes with missing dates (after): {stats['statutes_with_missing_dates_after']}")
    print(f"✅ Dates filled from Excel: {stats['dates_filled_from_excel']}")
    print(f"🔄 Statutes updated: {stats['statutes_updated']}")
    print(f"⏭️ Statutes unchanged: {stats['statutes_unchanged']}")
    
    matching = metadata["matching_analysis"]
    print(f"\n🔍 Matching Analysis:")
    print(f"   Exact matches: {matching['exact_matches']}")
    print(f"   Unmatched Excel statutes: {matching['unmatched_excel_statutes']}")
    print(f"   Unmatched DB statutes: {matching['unmatched_db_statutes']}")
    
    excel = metadata["excel_analysis"]
    print(f"\n📊 Excel Analysis:")
    print(f"   Total Excel rows: {excel['total_excel_rows']}")
    print(f"   Valid Excel rows: {excel['valid_excel_rows']}")
    print(f"   Invalid Excel rows: {excel['invalid_excel_rows']}")
    
    if metadata["date_analysis"]["date_range"]["earliest"]:
        print(f"\n📅 Date Range:")
        print(f"   Earliest: {metadata['date_analysis']['date_range']['earliest']}")
        print(f"   Latest: {metadata['date_analysis']['date_range']['latest']}")
    
    print(f"\n💾 Output:")
    print(f"   Source: {metadata['source_database']}")
    print(f"   Target: {metadata['target_database']}")
    print("="*60)

def find_excel_file_for_batch(batch_name: str) -> str:
    """Find the appropriate Excel file for the given batch name"""
    excel_dir = "04_date_processing/organized_excels"
    
    # Look for files with the batch name
    possible_patterns = [
        f"statutes_missing_date_gpt_Batched-Statutes_{batch_name}.xlsx",
        f"statutes_missing_date_gpt_Batched-Statutes-{batch_name}.xlsx",
        f"statutes_missing_date_gpt_{batch_name}.xlsx"
    ]
    
    for pattern in possible_patterns:
        file_path = os.path.join(excel_dir, pattern)
        if os.path.exists(file_path):
            return file_path
    
    # If no exact match, try to find any file with the batch number
    batch_number = batch_name.replace("batch", "")
    for filename in os.listdir(excel_dir):
        if filename.endswith(".xlsx") and batch_number in filename:
            return os.path.join(excel_dir, filename)
    
    raise FileNotFoundError(f"No Excel file found for batch '{batch_name}' in {excel_dir}")

def main():
    """Main execution function"""
    # Declare globals at the start
    global SOURCE_DB, SOURCE_COLL, TARGET_DB, TARGET_COLL
    
    parser = argparse.ArgumentParser(description="Fill missing dates in grouped batch databases from Excel file")
    parser.add_argument("--excel-file", help="Path to Excel file containing statute-date mappings (auto-detected if not provided)")
    parser.add_argument("--source-db", default="Batch-Base-Grouped", help="Source database name")
    parser.add_argument("--source-coll", default=SOURCE_COLL, help="Source collection name (e.g., batch1, batch2)")
    parser.add_argument("--target-db", default=None, help="Target database name (default: <source_db>-Filled)")
    parser.add_argument("--target-coll", default=None, help="Target collection name (default: same as source collection)")
    parser.add_argument("--output-dir", default="metadata", help="Output directory for metadata")
    parser.add_argument("--exports-dir", default="exports", help="Output directory for exports")
    
    args = parser.parse_args()
    
    # Update config with command line arguments
    SOURCE_DB = args.source_db
    SOURCE_COLL = args.source_coll

    # Use naming convention if not explicitly set
    if args.target_db is not None:
        TARGET_DB = args.target_db
    else:
        TARGET_DB = f"{SOURCE_DB}-Filled"
    if args.target_coll is not None:
        TARGET_COLL = args.target_coll
    else:
        TARGET_COLL = SOURCE_COLL

    # Update metadata
    metadata["source_database"] = f"{SOURCE_DB}.{SOURCE_COLL}"
    metadata["target_database"] = f"{TARGET_DB}.{TARGET_COLL}"
    
    try:
        log_info("Starting Fill Dates Grouped Batches process")
        
        # Auto-detect Excel file if not provided
        if args.excel_file:
            excel_file_path = args.excel_file
        else:
            excel_file_path = find_excel_file_for_batch(SOURCE_COLL)
            log_info(f"Auto-detected Excel file: {excel_file_path}")
        
        # Connect to MongoDB
        client = connect_to_mongodb()
        if not client:
            return
        
        # Load Excel data
        excel_data = load_excel_data(excel_file_path)
        
        # Get grouped statutes from database
        groups, statutes, missing_dates_before = get_grouped_statutes_with_missing_dates(client)
        metadata["processing_stats"]["statutes_with_missing_dates_before"] = missing_dates_before
        
        # Match statutes to Excel data
        matched_statutes, unmatched_excel, unmatched_db = match_statutes_to_excel(statutes, excel_data)
        
        # Update grouped statutes with dates
        updated_groups = update_grouped_statutes_with_dates(groups, matched_statutes)
        
        # Save to new collection
        save_to_new_collection(client, updated_groups)
        
        # Generate metadata
        generate_metadata_summary(groups, statutes, excel_data, matched_statutes, unmatched_excel, unmatched_db)
        
        # Save metadata and exports
        metadata_file = save_metadata_to_file(metadata, args.output_dir)
        save_unmatched_statutes(unmatched_excel, unmatched_db, args.exports_dir)
        
        # Print summary
        print_summary(metadata)
        
        log_info("Fill Dates Grouped Batches process completed successfully")
        
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