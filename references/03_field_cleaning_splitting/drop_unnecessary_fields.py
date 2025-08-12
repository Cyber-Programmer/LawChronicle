from pymongo import MongoClient
from tqdm import tqdm
import json
from datetime import datetime, date
import os
import numpy as np
from collections import defaultdict, Counter

# --- CONFIG ---
MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "Batched-Statutes"
COLL_NAME = "batch10"

FIELDS_TO_DROP = [
    "Source", "Category", "PDF_URL", "Blob_Url"
]
SECTION_FIELDS_TO_DROP = [
    "Statute_RAG_Content", "Statute_HTML"
]

# Initialize metadata tracking
metadata = {
    "total_statutes_processed": 0,
    "statutes_updated": 0,
    "fields_removed": {
        "top_level": Counter(),
        "section_level": Counter()
    },
    "processing_stats": {
        "total_sections_processed": 0,
        "sections_with_removals": 0,
        "average_sections_per_statute": 0
    },
    "removal_details": {
        "top_level_fields_found": defaultdict(int),
        "section_fields_found": defaultdict(int),
        "sample_removals": []
    },
    "field_analysis": {
        "statutes_with_top_level_removals": 0,
        "statutes_with_section_removals": 0,
        "statutes_with_both_removals": 0
    }
}

client = MongoClient(MONGO_URI)
col = client[DB_NAME][COLL_NAME]

# Fetch all documents and convert to numpy array for faster processing
docs = list(col.find())
total_docs = len(docs)

# Convert field lists to numpy arrays for faster lookups
fields_to_drop_array = np.array(FIELDS_TO_DROP)
section_fields_to_drop_array = np.array(SECTION_FIELDS_TO_DROP)

print(f"🔍 Processing {total_docs} statutes from {DB_NAME}.{COLL_NAME}...")
print(f"📋 Top-level fields to drop: {FIELDS_TO_DROP}")
print(f"📋 Section-level fields to drop: {SECTION_FIELDS_TO_DROP}")

for doc in tqdm(docs, desc="Dropping unnecessary fields"):
    metadata["total_statutes_processed"] += 1
    statute_name = doc.get("Statute_Name", "UNKNOWN")
    sections = doc.get("Sections", [])
    
    metadata["processing_stats"]["total_sections_processed"] += len(sections)
    
    # Track what was found before removal
    top_level_removals = []
    section_removals = []
    
    # Drop top-level fields using numpy for faster field checking
    doc_fields = np.array(list(doc.keys()))
    fields_to_remove = np.intersect1d(doc_fields, fields_to_drop_array)
    
    for field in fields_to_remove:
        metadata["fields_removed"]["top_level"][field] += 1
        metadata["removal_details"]["top_level_fields_found"][field] += 1
        top_level_removals.append(field)
        doc.pop(field, None)
    
    # Track section-level removals using numpy for faster field checking
    sections_with_removals = 0
    if "Sections" in doc and isinstance(doc["Sections"], list):
        for section in doc["Sections"]:
            section_removals_for_this_section = []
            section_fields = np.array(list(section.keys()))
            section_fields_to_remove = np.intersect1d(section_fields, section_fields_to_drop_array)
            
            for sfield in section_fields_to_remove:
                metadata["fields_removed"]["section_level"][sfield] += 1
                metadata["removal_details"]["section_fields_found"][sfield] += 1
                section_removals_for_this_section.append(sfield)
                section.pop(sfield, None)
            
            if section_removals_for_this_section:
                sections_with_removals += 1
                section_removals.extend(section_removals_for_this_section)
    
    metadata["processing_stats"]["sections_with_removals"] += sections_with_removals
    
    # Track removal patterns
    has_top_level_removals = len(top_level_removals) > 0
    has_section_removals = len(section_removals) > 0
    
    if has_top_level_removals:
        metadata["field_analysis"]["statutes_with_top_level_removals"] += 1
    if has_section_removals:
        metadata["field_analysis"]["statutes_with_section_removals"] += 1
    if has_top_level_removals and has_section_removals:
        metadata["field_analysis"]["statutes_with_both_removals"] += 1
    
    # Store sample removals (first 10)
    if len(metadata["removal_details"]["sample_removals"]) < 10:
        sample_removal = {
            "statute_name": statute_name,
            "top_level_removals": top_level_removals,
            "section_removals": list(set(section_removals)),  # Remove duplicates
            "sections_affected": sections_with_removals,
            "total_sections": len(sections)
        }
        metadata["removal_details"]["sample_removals"].append(sample_removal)
    
    # Update document in DB
    col.replace_one({"_id": doc["_id"]}, doc)
    metadata["statutes_updated"] += 1

# Calculate averages
if metadata["total_statutes_processed"] > 0:
    metadata["processing_stats"]["average_sections_per_statute"] = (
        metadata["processing_stats"]["total_sections_processed"] / metadata["total_statutes_processed"]
    )

print(f"\n📊 FIELD REMOVAL METADATA:")
print("=" * 50)
print(f"📋 Total statutes processed: {metadata['total_statutes_processed']}")
print(f"📋 Statutes updated: {metadata['statutes_updated']}")
print(f"📋 Total top-level fields removed: {sum(metadata['fields_removed']['top_level'].values())}")
print(f"📋 Total section-level fields removed: {sum(metadata['fields_removed']['section_level'].values())}")

print(f"\n📊 Processing Statistics:")
print(f"   - Total sections processed: {metadata['processing_stats']['total_sections_processed']}")
print(f"   - Sections with removals: {metadata['processing_stats']['sections_with_removals']}")
print(f"   - Average sections per statute: {metadata['processing_stats']['average_sections_per_statute']:.2f}")

print(f"\n📊 Top-Level Field Removals:")
for field_name, count in metadata["fields_removed"]["top_level"].most_common():
    print(f"   - {field_name}: {count} times")

print(f"\n📊 Section-Level Field Removals:")
for field_name, count in metadata["fields_removed"]["section_level"].most_common():
    print(f"   - {field_name}: {count} times")

print(f"\n📊 Removal Patterns:")
print(f"   - Statutes with top-level removals: {metadata['field_analysis']['statutes_with_top_level_removals']}")
print(f"   - Statutes with section removals: {metadata['field_analysis']['statutes_with_section_removals']}")
print(f"   - Statutes with both types: {metadata['field_analysis']['statutes_with_both_removals']}")

print(f"\n📊 Sample Removals (first 5):")
for i, removal in enumerate(metadata["removal_details"]["sample_removals"][:5]):
    print(f"   {i+1}. {removal['statute_name']}:")
    if removal['top_level_removals']:
        print(f"      Top-level: {', '.join(removal['top_level_removals'])}")
    if removal['section_removals']:
        print(f"      Section-level: {', '.join(removal['section_removals'])}")
    print(f"      Sections affected: {removal['sections_affected']}/{removal['total_sections']}")

# Add script/db/collection/date info to metadata
metadata["script"] = "drop_unnecessary_fields.py"
metadata["db_name"] = DB_NAME
metadata["collection"] = COLL_NAME
metadata["date"] = date.today().isoformat()

# Save metadata to metadata/ folder with new naming convention
metadata_dir = "metadata"
os.makedirs(metadata_dir, exist_ok=True)
meta_filename = f"metadata_drop_unnecessary_fields_{DB_NAME}_{COLL_NAME}_{date.today().isoformat()}.json"
meta_path = os.path.join(metadata_dir, meta_filename)
with open(meta_path, "w", encoding="utf-8") as f:
    json.dump(metadata, f, ensure_ascii=False, indent=2)

print(f"\n✅ Updated {metadata['statutes_updated']} statutes in {DB_NAME}.{COLL_NAME}.")
print(f"📊 Metadata saved to {meta_path}")

client.close()
