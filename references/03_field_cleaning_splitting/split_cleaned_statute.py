import math
from pymongo import MongoClient
from tqdm import tqdm
import json
from datetime import datetime, date
import os
import numpy as np
from collections import defaultdict, Counter

# --- CONFIG ---
SRC_DB = "Statutes"
SRC_COLL = "normalized_statutes"
SPLIT_DB_PREFIX = "Batched-Statutes"
SPLIT_COLL = "batch"
NUM_SPLITS = 10

# Initialize metadata tracking
metadata = {
    "total_statutes_processed": 0,
    "splits_created": 0,
    "splitting_stats": {
        "base_chunk_size": 0,
        "last_chunk_size": 0,
        "chunk_sizes": [],
        "total_sections_distributed": 0,
        "average_sections_per_statute": 0
    },
    "database_distribution": {
        "statutes_per_database": {},
        "sections_per_database": {},
        "database_sizes": {}
    },
    "content_analysis": {
        "statutes_with_preamble": 0,
        "statutes_with_multiple_sections": 0,
        "section_count_distribution": Counter(),
        "sample_statutes_by_split": {}
    },
    "processing_details": {
        "databases_cleared": 0,
        "total_documents_inserted": 0,
        "insertion_errors": 0
    }
}

# --- Main script ---
def analyze_statute_content(statute):
    """Analyze the content of a statute for metadata tracking using numpy for faster operations"""
    sections = statute.get("Sections", [])
    section_count = len(sections)
    
    # Check for preamble using numpy for faster string comparison
    has_preamble = False
    if sections:
        section_names = np.array([section.get("Section", "").strip().upper() for section in sections])
        has_preamble = np.any(np.char.equal(section_names, "PREAMBLE"))
    
    return {
        "section_count": section_count,
        "has_preamble": has_preamble,
        "has_multiple_sections": section_count > 1
    }

def main():
    print("Connecting to MongoDB...")
    client = MongoClient("mongodb://localhost:27017/")
    src_coll = client[SRC_DB][SRC_COLL]

    print("Fetching all statutes from source collection...")
    statutes = list(src_coll.find({}))
    total = len(statutes)
    metadata["total_statutes_processed"] = total
    print(f"Fetched {total} statutes.")

    # Analyze content before splitting
    print("Analyzing statute content...")
    total_sections = 0
    for statute in statutes:
        analysis = analyze_statute_content(statute)
        total_sections += analysis["section_count"]
        metadata["content_analysis"]["section_count_distribution"][analysis["section_count"]] += 1
        
        if analysis["has_preamble"]:
            metadata["content_analysis"]["statutes_with_preamble"] += 1
        if analysis["has_multiple_sections"]:
            metadata["content_analysis"]["statutes_with_multiple_sections"] += 1
    
    metadata["splitting_stats"]["total_sections_distributed"] = total_sections
    metadata["splitting_stats"]["average_sections_per_statute"] = total_sections / total if total > 0 else 0

    # Calculate chunk sizes
    base_size = total // NUM_SPLITS
    last_size = total - base_size * (NUM_SPLITS - 1)
    sizes = [base_size] * (NUM_SPLITS - 1) + [last_size]
    
    metadata["splitting_stats"]["base_chunk_size"] = base_size
    metadata["splitting_stats"]["last_chunk_size"] = last_size
    metadata["splitting_stats"]["chunk_sizes"] = sizes

    print(f"Splitting into {NUM_SPLITS} databases: {sizes} entities each.")

    start = 0
    for i, size in enumerate(tqdm(sizes, desc="Splitting statutes")):
        db_name = f"{SPLIT_DB_PREFIX}{i+1}"
        split_coll = client[db_name][SPLIT_COLL]
        
        print(f"Writing {size} statutes to {db_name}.{SPLIT_COLL} ...")
        
        # Clear target collection first
        split_coll.delete_many({})
        metadata["processing_details"]["databases_cleared"] += 1
        
        chunk = statutes[start:start+size]
        chunk_sections = 0
        sample_statutes = []
        
        for doc in tqdm(chunk, desc=f"Inserting into {db_name}"):
            # Analyze this statute
            analysis = analyze_statute_content(doc)
            chunk_sections += analysis["section_count"]
            
            # Store sample statutes (first 3 from each split)
            if len(sample_statutes) < 3:
                sample_statutes.append({
                    "statute_name": doc.get("Statute_Name", "UNKNOWN"),
                    "section_count": analysis["section_count"],
                    "has_preamble": analysis["has_preamble"]
                })
            
            # Insert document
            try:
                doc_copy = doc.copy()
                doc_copy.pop("_id", None)
                split_coll.insert_one(doc_copy)
                metadata["processing_details"]["total_documents_inserted"] += 1
            except Exception as e:
                metadata["processing_details"]["insertion_errors"] += 1
                print(f"Error inserting document: {e}")
        
        # Store metadata for this database
        metadata["database_distribution"]["statutes_per_database"][db_name] = size
        metadata["database_distribution"]["sections_per_database"][db_name] = chunk_sections
        metadata["database_distribution"]["database_sizes"][db_name] = {
            "statutes": size,
            "sections": chunk_sections,
            "average_sections_per_statute": chunk_sections / size if size > 0 else 0
        }
        metadata["content_analysis"]["sample_statutes_by_split"][db_name] = sample_statutes
        
        start += size
        metadata["splits_created"] += 1

    print(f"\n📊 STATUTE SPLITTING METADATA:")
    print("=" * 50)
    print(f"📋 Total statutes processed: {metadata['total_statutes_processed']}")
    print(f"📋 Splits created: {metadata['splits_created']}")
    print(f"📋 Total sections distributed: {metadata['splitting_stats']['total_sections_distributed']}")
    print(f"📋 Average sections per statute: {metadata['splitting_stats']['average_sections_per_statute']:.2f}")

    print(f"\n📊 Splitting Configuration:")
    print(f"   - Base chunk size: {metadata['splitting_stats']['base_chunk_size']}")
    print(f"   - Last chunk size: {metadata['splitting_stats']['last_chunk_size']}")
    print(f"   - Chunk sizes: {metadata['splitting_stats']['chunk_sizes']}")

    print(f"\n📊 Content Analysis:")
    print(f"   - Statutes with preamble: {metadata['content_analysis']['statutes_with_preamble']}")
    print(f"   - Statutes with multiple sections: {metadata['content_analysis']['statutes_with_multiple_sections']}")

    print(f"\n📊 Section Count Distribution (top 5):")
    for section_count, count in metadata["content_analysis"]["section_count_distribution"].most_common(5):
        print(f"   - {section_count} sections: {count} statutes")

    print(f"\n📊 Database Distribution:")
    for db_name, stats in metadata["database_distribution"]["database_sizes"].items():
        print(f"   - {db_name}: {stats['statutes']} statutes, {stats['sections']} sections")

    print(f"\n📊 Processing Details:")
    print(f"   - Databases cleared: {metadata['processing_details']['databases_cleared']}")
    print(f"   - Total documents inserted: {metadata['processing_details']['total_documents_inserted']}")
    print(f"   - Insertion errors: {metadata['processing_details']['insertion_errors']}")

    print(f"\n📊 Sample Statutes by Split (first 3 from each):")
    for db_name, samples in metadata["content_analysis"]["sample_statutes_by_split"].items():
        print(f"   {db_name}:")
        for sample in samples:
            preamble_info = " (has preamble)" if sample["has_preamble"] else ""
            print(f"     - {sample['statute_name']}: {sample['section_count']} sections{preamble_info}")

    # Add script/db/collection/date info to metadata
    metadata["script"] = "split_cleaned_statute.py"
    metadata["db_name"] = SRC_DB
    metadata["collection"] = SRC_COLL
    metadata["date"] = date.today().isoformat()

    # Save metadata to metadata/ folder with new naming convention
    metadata_dir = "metadata"
    os.makedirs(metadata_dir, exist_ok=True)
    meta_filename = f"metadata_split_cleaned_statute_{SRC_DB}_{SRC_COLL}_{date.today().isoformat()}.json"
    meta_path = os.path.join(metadata_dir, meta_filename)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print(f"\n✅ All splits completed successfully.")
    print(f"📊 Metadata saved to {meta_path}")

if __name__ == "__main__":
    main()
