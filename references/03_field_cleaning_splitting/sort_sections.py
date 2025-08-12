from pymongo import MongoClient
from tqdm import tqdm
import re
import time
import json
from datetime import datetime, date
import os
import numpy as np
from collections import defaultdict, Counter

# --- CONFIG ---
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "Batched-Statutes"
BATCHES = [f"batch{i}" for i in range(1, 11)]  # batch1 to batch10

def section_sort_key(section):
    """
    Sort key function for sections using numpy for faster string operations.
    """
    sec = section.get("Section", "")
    sec_lower = sec.lower()
    if np.char.equal(sec_lower, "preamble"):
        return (0, "")
    match = re.match(r"(\d+)", str(sec))
    if match:
        return (1, int(match.group(1)))
    return (2, sec)

def analyze_section_type(section):
    """Analyze the type of a section for metadata tracking using numpy for faster string operations"""
    sec = section.get("Section", "")
    sec_lower = sec.lower()
    if np.char.equal(sec_lower, "preamble"):
        return "preamble"
    match = re.match(r"(\d+)", str(sec))
    if match:
        return "numeric"
    return "text"

def process_batch(coll_name):
    # Initialize metadata tracking for this batch
    metadata = {
        "total_statutes_processed": 0,
        "statutes_with_multiple_sections": 0,
        "statutes_updated": 0,
        "sorting_stats": {
            "total_sections_processed": 0,
            "sections_sorted": 0,
            "preamble_sections_found": 0,
            "numeric_sections_found": 0,
            "text_sections_found": 0
        },
        "sorting_details": {
            "statutes_with_preamble_first": 0,
            "statutes_with_numeric_first": 0,
            "statutes_with_text_first": 0,
            "section_order_changes": []
        },
        "section_analysis": {
            "section_types_by_statute": defaultdict(list),
            "sample_sorting_changes": []
        }
    }

    client = MongoClient(MONGO_URI)
    col = client[DB_NAME][coll_name]
    print(f"\nConnected to MongoDB database: {DB_NAME}, collection: {coll_name}")

    # Fetch all statutes
    statutes = list(col.find({}))
    total_statutes = len(statutes)
    print(f"🔍 Processing {total_statutes} statutes from {DB_NAME}.{coll_name}...")

    updated = 0
    for idx, doc in enumerate(tqdm(statutes, desc=f"Checking and sorting all sections in {coll_name}")):
        metadata["total_statutes_processed"] += 1
        statute_name = doc.get("Statute_Name", "")
        sections = doc.get("Sections", [])

        if not sections or len(sections) == 1:
            continue

        metadata["statutes_with_multiple_sections"] += 1
        metadata["sorting_stats"]["total_sections_processed"] += len(sections)

        # Analyze section types for this statute
        section_types = []
        for section in sections:
            section_type = analyze_section_type(section)
            section_types.append(section_type)
            metadata["sorting_stats"][f"{section_type}_sections_found"] += 1

        metadata["section_analysis"]["section_types_by_statute"][statute_name] = section_types

        # Sort all sections
        sorted_sections = sorted(sections, key=section_sort_key)

        # Track sorting changes
        if sections != sorted_sections:
            metadata["statutes_updated"] += 1
            metadata["sorting_stats"]["sections_sorted"] += len(sections)

            # Track what type of section is now first
            sorted_first_type = analyze_section_type(sorted_sections[0]) if sorted_sections else "none"
            if sorted_first_type == "preamble":
                metadata["sorting_details"]["statutes_with_preamble_first"] += 1
            elif sorted_first_type == "numeric":
                metadata["sorting_details"]["statutes_with_numeric_first"] += 1
            elif sorted_first_type == "text":
                metadata["sorting_details"]["statutes_with_text_first"] += 1

            # Store detailed change information
            change_detail = {
                "statute_name": statute_name,
                "original_order": [s.get("Section", "") for s in sections],
                "sorted_order": [s.get("Section", "") for s in sorted_sections],
                "original_types": [analyze_section_type(s) for s in sections[:2]],
                "sorted_types": [analyze_section_type(s) for s in sorted_sections[:2]]
            }
            metadata["sorting_details"]["section_order_changes"].append(change_detail)

            # Store sample changes (first 10)
            if len(metadata["section_analysis"]["sample_sorting_changes"]) < 10:
                sample_change = {
                    "statute_name": statute_name,
                    "before": [s.get("Section", "") for s in sections],
                    "after": [s.get("Section", "") for s in sorted_sections],
                    "change_description": f"{analyze_section_type(sections[0]) if sections else 'none'} → {analyze_section_type(sorted_sections[0]) if sorted_sections else 'none'}"
                }
                metadata["section_analysis"]["sample_sorting_changes"].append(sample_change)

            print(f"  -> Updating order for: {statute_name}")
            col.update_one({"_id": doc["_id"]}, {"$set": {"Sections": sorted_sections}})
            updated += 1

    print(f"\n📊 SECTION SORTING METADATA for {coll_name}:")
    print("=" * 50)
    print(f"📋 Total statutes processed: {metadata['total_statutes_processed']}")
    print(f"📋 Statutes with multiple sections: {metadata['statutes_with_multiple_sections']}")
    print(f"📋 Statutes updated: {metadata['statutes_updated']}")
    print(f"📋 Total sections processed: {metadata['sorting_stats']['total_sections_processed']}")
    print(f"📋 Sections sorted: {metadata['sorting_stats']['sections_sorted']}")

    print(f"\n📊 Section Type Analysis:")
    print(f"   - Preamble sections found: {metadata['sorting_stats']['preamble_sections_found']}")
    print(f"   - Numeric sections found: {metadata['sorting_stats']['numeric_sections_found']}")
    print(f"   - Text sections found: {metadata['sorting_stats']['text_sections_found']}")

    print(f"\n📊 Sorting Results:")
    print(f"   - Statutes with preamble first: {metadata['sorting_details']['statutes_with_preamble_first']}")
    print(f"   - Statutes with numeric first: {metadata['sorting_details']['statutes_with_numeric_first']}")
    print(f"   - Statutes with text first: {metadata['sorting_details']['statutes_with_text_first']}")

    print(f"\n📊 Sample Sorting Changes (first 5):")
    for i, change in enumerate(metadata["section_analysis"]["sample_sorting_changes"][:5]):
        print(f"   {i+1}. {change['statute_name']}:")
        print(f"      Before: {change['before']}")
        print(f"      After: {change['after']}")
        print(f"      Change: {change['change_description']}")

    # Calculate additional statistics
    if metadata["statutes_with_multiple_sections"] > 0:
        update_rate = (metadata["statutes_updated"] / metadata["statutes_with_multiple_sections"]) * 100
        print(f"\n📊 Update Rate: {update_rate:.1f}% of multi-section statutes needed sorting")

    # Add script/db/collection/date info to metadata
    metadata["script"] = "sort_sections.py"
    metadata["db_name"] = DB_NAME
    metadata["collection"] = coll_name
    metadata["date"] = date.today().isoformat()

    # Save metadata to metadata/ folder with new naming convention
    metadata_dir = "metadata"
    os.makedirs(metadata_dir, exist_ok=True)
    meta_filename = f"metadata_sort_sections_{DB_NAME}_{coll_name}_{date.today().isoformat()}.json"
    meta_path = os.path.join(metadata_dir, meta_filename)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Sorted the first two sections in {updated} statutes (if needed). Preamble always on top.")
    print(f"📊 Metadata saved to {meta_path}")

    client.close()

if __name__ == "__main__":
    print("Starting section sorting for all 10 batches...\n")
    for i, batch in enumerate(BATCHES, 1):
        print(f"\n{'='*60}\n[{i}/10] Processing {batch}...\n{'='*60}")
        process_batch(batch)
    print("\nAll batches processed.")