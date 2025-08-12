"""
This script cleans up statutes in the normalized MongoDB collection that have a single empty section,
by moving relevant top-level fields into Sections[0] and removing unwanted fields from the top level.

Reference: See bring_common_fields_up.py and drop_unnecessary_fields.py for field handling patterns.
"""

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
COLL_NAME = "batch1"

# Fields to move into Sections[0] if present at top level - converted to numpy arrays for faster lookups
SECTION_FIELDS = np.array([
    "Section", "Definition", "Citations", "Statute", "Text", "Title", "Subsection", "Bookmark_ID"
])

# Fields to remove from top level if present (unwanted fields) - converted to numpy arrays for faster lookups
FIELDS_TO_REMOVE = np.array([
    "Source", "Category", "PDF_URL", "Blob_Url", "Statute_RAG_Content", "Statute_HTML"
])

# Initialize metadata tracking
metadata = {
    "total_statutes_processed": 0,
    "statutes_with_single_section": 0,
    "statutes_with_empty_single_section": 0,
    "statutes_updated": 0,
    "fields_moved": {
        "section_fields": Counter(),
        "removed_fields": Counter()
    },
    "processing_stats": {
        "total_fields_moved": 0,
        "total_fields_removed": 0,
        "statutes_with_section_field": 0,
        "statutes_with_definition_field": 0,
        "statutes_with_citations_field": 0
    },
    "field_analysis": {
        "statutes_with_preamble_section": 0,
        "statutes_with_preamble_definition": 0,
        "statutes_with_empty_citations": 0
    },
    "sample_updates": []
}

client = MongoClient(MONGO_URI)
col = client[DB_NAME][COLL_NAME]

def is_single_empty_section(sections):
    """
    Returns True if sections is a list of length 1 and the only section is empty or has only null/empty values.
    """
    if not isinstance(sections, list) or len(sections) != 1:
        return False
    section = sections[0]
    if not isinstance(section, dict):
        return False
    # Consider section empty if all values are None, empty string, or empty list/dict
    for v in section.values():
        if v not in (None, "", [], {}):
            return False
    return True

# Query for statutes with a single section (possibly empty)
query = {
    "Sections": {"$type": "array", "$size": 1}
}

docs = list(col.find(query))
total_docs = len(docs)

print(f"🔍 Found {total_docs} statutes with single section array.")
print(f"📋 Section fields to move: {SECTION_FIELDS}")
print(f"📋 Fields to remove: {FIELDS_TO_REMOVE}")

for doc in tqdm(docs, desc="Fixing single-section statutes"):
    metadata["total_statutes_processed"] += 1
    statute_name = doc.get("Statute_Name", "UNKNOWN")
    sections = doc.get("Sections", [])
    
    metadata["statutes_with_single_section"] += 1
    
    if not is_single_empty_section(sections):
        continue  # Only process if the single section is empty
    
    metadata["statutes_with_empty_single_section"] += 1
    
    # Track what fields were found and moved
    fields_moved = []
    fields_removed = []
    
    # Prepare the new section dict from top-level fields using numpy for faster field checking
    new_section = {}
    doc_fields = np.array(list(doc.keys()))
    section_fields_to_move = np.intersect1d(doc_fields, SECTION_FIELDS)
    
    for field in section_fields_to_move:
        new_section[field] = doc[field]
        fields_moved.append(field)
        metadata["fields_moved"]["section_fields"][field] += 1
        metadata["processing_stats"]["total_fields_moved"] += 1
        
        # Track specific field statistics
        if field == "Section":
            metadata["processing_stats"]["statutes_with_section_field"] += 1
        elif field == "Definition":
            metadata["processing_stats"]["statutes_with_definition_field"] += 1
        elif field == "Citations":
            metadata["processing_stats"]["statutes_with_citations_field"] += 1

    # If Citations is None, set as empty list for consistency
    if "Citations" in new_section and new_section["Citations"] is None:
        new_section["Citations"] = []
        metadata["field_analysis"]["statutes_with_empty_citations"] += 1

    # If Section is missing, but Definition or Statute is present, set Section as "Preamble"
    if "Section" not in new_section:
        new_section["Section"] = "Preamble"
        metadata["field_analysis"]["statutes_with_preamble_section"] += 1

    # If Definition is missing, but Section is "Preamble", set Definition as "Preamble"
    if "Definition" not in new_section and new_section.get("Section", "").lower() == "preamble":
        new_section["Definition"] = "Preamble"
        metadata["field_analysis"]["statutes_with_preamble_definition"] += 1

    # Track fields that will be removed using numpy for faster field checking
    fields_to_remove = np.intersect1d(doc_fields, FIELDS_TO_REMOVE)
    for field in fields_to_remove:
        fields_removed.append(field)
        metadata["fields_moved"]["removed_fields"][field] += 1
        metadata["processing_stats"]["total_fields_removed"] += 1

    # Store sample updates (first 10)
    if len(metadata["sample_updates"]) < 10:
        sample_update = {
            "statute_name": statute_name,
            "fields_moved_to_section": fields_moved,
            "fields_removed": fields_removed,
            "new_section_content": new_section
        }
        metadata["sample_updates"].append(sample_update)

    # Build update dict
    update = {}

    # Set the Sections array to the new section
    update["$set"] = {"Sections": [new_section]}

    # Remove the top-level fields that have been moved into Sections
    unset_fields = {}
    for field in SECTION_FIELDS:
        if field in doc:
            unset_fields[field] = ""
    # Also remove unwanted fields
    for field in FIELDS_TO_REMOVE:
        if field in doc:
            unset_fields[field] = ""
    if unset_fields:
        update["$unset"] = unset_fields

    # Apply the update
    col.update_one({"_id": doc["_id"]}, update)
    metadata["statutes_updated"] += 1

print(f"\n📊 SINGLE-SECTION CLEANUP METADATA:")
print("=" * 50)
print(f"📋 Total statutes processed: {metadata['total_statutes_processed']}")
print(f"📋 Statutes with single section: {metadata['statutes_with_single_section']}")
print(f"📋 Statutes with empty single section: {metadata['statutes_with_empty_single_section']}")
print(f"📋 Statutes updated: {metadata['statutes_updated']}")

print(f"\n📊 Field Movement Statistics:")
print(f"   - Total fields moved to sections: {metadata['processing_stats']['total_fields_moved']}")
print(f"   - Total fields removed: {metadata['processing_stats']['total_fields_removed']}")
print(f"   - Average fields moved per statute: {metadata['processing_stats']['total_fields_moved'] / max(metadata['statutes_updated'], 1):.2f}")

print(f"\n📊 Section Fields Moved:")
for field_name, count in metadata["fields_moved"]["section_fields"].most_common():
    print(f"   - {field_name}: {count} times")

print(f"\n📊 Fields Removed:")
for field_name, count in metadata["fields_moved"]["removed_fields"].most_common():
    print(f"   - {field_name}: {count} times")

print(f"\n📊 Field Analysis:")
print(f"   - Statutes with Section field: {metadata['processing_stats']['statutes_with_section_field']}")
print(f"   - Statutes with Definition field: {metadata['processing_stats']['statutes_with_definition_field']}")
print(f"   - Statutes with Citations field: {metadata['processing_stats']['statutes_with_citations_field']}")

print(f"\n📊 Special Handling:")
print(f"   - Statutes with Preamble section: {metadata['field_analysis']['statutes_with_preamble_section']}")
print(f"   - Statutes with Preamble definition: {metadata['field_analysis']['statutes_with_preamble_definition']}")
print(f"   - Statutes with empty citations: {metadata['field_analysis']['statutes_with_empty_citations']}")

print(f"\n📊 Sample Updates (first 5):")
for i, update in enumerate(metadata["sample_updates"][:5]):
    print(f"   {i+1}. {update['statute_name']}:")
    if update['fields_moved_to_section']:
        print(f"      Moved to section: {', '.join(update['fields_moved_to_section'])}")
    if update['fields_removed']:
        print(f"      Removed: {', '.join(update['fields_removed'])}")

# Add script/db/collection/date info to metadata
metadata["script"] = "cleaning_single_section.py"
metadata["db_name"] = DB_NAME
metadata["collection"] = COLL_NAME
metadata["date"] = date.today().isoformat()

# Save metadata to metadata/ folder with new naming convention
metadata_dir = "metadata"
os.makedirs(metadata_dir, exist_ok=True)
meta_filename = f"metadata_cleaning_single_section_{DB_NAME}_{COLL_NAME}_{date.today().isoformat()}.json"
meta_path = os.path.join(metadata_dir, meta_filename)
with open(meta_path, "w", encoding="utf-8") as f:
    json.dump(metadata, f, ensure_ascii=False, indent=2)

print(f"\n✅ Updated {metadata['statutes_updated']} single-section statutes.")
print(f"📊 Metadata saved to {meta_path}")

client.close()

