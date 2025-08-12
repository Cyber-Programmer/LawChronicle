"""
Bring common fields in all sections up to the statute level, updating the normalized MongoDB collection in place.

- For each statute in the normalized DB:
    - Find fields that are present in every section and have the same value in all sections.
    - Move those fields up to the statute level (as top-level fields).
    - Remove those fields from each section.
    - Update the document in the DB.
"""

from pymongo import MongoClient
from tqdm import tqdm
import json
from datetime import datetime, date
from collections import defaultdict, Counter
import os
import numpy as np

MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "Batched-Statutes"
COLL_NAME = "batch10"

# Initialize metadata tracking
metadata = {
    "total_statutes_processed": 0,
    "statutes_with_common_fields": 0,
    "statutes_updated": 0,
    "total_fields_moved": 0,
    "fields_moved_by_statute": {},
    "field_frequency": Counter(),
    "field_value_lengths": defaultdict(list),
    "processing_stats": {
        "total_sections_processed": 0,
        "average_sections_per_statute": 0,
        "statutes_with_no_common_fields": 0
    },
    "sample_movements": []
}

client = MongoClient(MONGO_URI)
coll = client[DB_NAME][COLL_NAME]

def find_common_fields(sections):
    """
    Returns a dict of fields that are present in every section and have the same value in all sections.
    Uses numpy for faster field comparison.
    """
    if not sections:
        return {}

    # Convert sections to numpy arrays for faster processing
    section_arrays = [np.array(list(section.items())) for section in sections]
    
    # Get all unique field names across all sections
    all_fields = set()
    for section in sections:
        all_fields.update(section.keys())
    
    all_fields = np.array(list(all_fields))
    common_fields = {}
    
    # Check each field for commonality
    for field in all_fields:
        field_values = []
        field_present_in_all = True
        
        for section in sections:
            if field in section:
                field_values.append(section[field])
            else:
                field_present_in_all = False
                break
        
        if field_present_in_all and len(set(field_values)) == 1:
            common_fields[field] = field_values[0]
    
    return common_fields

total = coll.count_documents({})
updated_count = 0

print(f"🔍 Processing {total} statutes from {DB_NAME}.{COLL_NAME}...")

for statute in tqdm(coll.find({}, projection=None), total=total, desc="Bringing up common fields"):
    metadata["total_statutes_processed"] += 1
    statute_name = statute.get("Statute_Name", "UNKNOWN")
    sections = statute.get("Sections", [])
    
    metadata["processing_stats"]["total_sections_processed"] += len(sections)
    
    common_fields = find_common_fields(sections)
    
    if common_fields:
        metadata["statutes_with_common_fields"] += 1
        
        # Track field movements for this statute
        statute_movements = {
            "statute_name": statute_name,
            "fields_moved": list(common_fields.keys()),
            "field_count": len(common_fields),
            "section_count": len(sections)
        }
        
        # Track field frequency and value lengths
        for field_name, field_value in common_fields.items():
            metadata["field_frequency"][field_name] += 1
            value_length = len(str(field_value)) if field_value else 0
            metadata["field_value_lengths"][field_name].append(value_length)
        
        # Store sample movements (first 10)
        if len(metadata["sample_movements"]) < 10:
            metadata["sample_movements"].append(statute_movements)
        
        # Remove these fields from each section
        for section in sections:
            for k in common_fields:
                section.pop(k, None)

        # Prepare update dict
        update_fields = {k: v for k, v in common_fields.items()}
        update_fields["Sections"] = sections

        # Update the document in the DB
        coll.update_one(
            {"_id": statute["_id"]},
            {"$set": update_fields}
        )
        updated_count += 1
        metadata["statutes_updated"] += 1
        metadata["total_fields_moved"] += len(common_fields)
        metadata["fields_moved_by_statute"][statute_name] = list(common_fields.keys())
    else:
        metadata["processing_stats"]["statutes_with_no_common_fields"] += 1

# Calculate averages
if metadata["total_statutes_processed"] > 0:
    metadata["processing_stats"]["average_sections_per_statute"] = (
        metadata["processing_stats"]["total_sections_processed"] / metadata["total_statutes_processed"]
    )

# Calculate field value length statistics
for field_name, lengths in metadata["field_value_lengths"].items():
    if lengths:
        metadata["field_value_lengths"][field_name] = {
            "min": min(lengths),
            "max": max(lengths),
            "avg": sum(lengths) / len(lengths),
            "count": len(lengths)
        }

print(f"\n📊 FIELD MOVEMENT METADATA:")
print("=" * 50)
print(f"📋 Total statutes processed: {metadata['total_statutes_processed']}")
print(f"📋 Statutes with common fields: {metadata['statutes_with_common_fields']}")
print(f"📋 Statutes updated: {metadata['statutes_updated']}")
print(f"📋 Total fields moved: {metadata['total_fields_moved']}")
print(f"📋 Average fields moved per statute: {metadata['total_fields_moved'] / max(metadata['statutes_updated'], 1):.2f}")

print(f"\n📊 Processing Statistics:")
print(f"   - Total sections processed: {metadata['processing_stats']['total_sections_processed']}")
print(f"   - Average sections per statute: {metadata['processing_stats']['average_sections_per_statute']:.2f}")
print(f"   - Statutes with no common fields: {metadata['processing_stats']['statutes_with_no_common_fields']}")

print(f"\n📊 Most Common Fields Moved:")
for field_name, count in metadata["field_frequency"].most_common(10):
    print(f"   - {field_name}: {count} times")

print(f"\n📊 Field Value Length Statistics:")
for field_name, stats in list(metadata["field_value_lengths"].items())[:5]:
    if isinstance(stats, dict):
        print(f"   - {field_name}: min={stats['min']}, max={stats['max']}, avg={stats['avg']:.1f}")

print(f"\n📊 Sample Field Movements (first 5):")
for i, movement in enumerate(metadata["sample_movements"][:5]):
    print(f"   {i+1}. {movement['statute_name']}: {movement['field_count']} fields moved")

# Add script/db/collection/date info to metadata
metadata["script"] = "bring_common_fields_up.py"
metadata["db_name"] = DB_NAME
metadata["collection"] = COLL_NAME
metadata["date"] = date.today().isoformat()

# Save metadata to metadata/ folder with new naming convention
metadata_dir = "metadata"
os.makedirs(metadata_dir, exist_ok=True)
meta_filename = f"metadata_bring_common_fields_up_{DB_NAME}_{COLL_NAME}_{date.today().isoformat()}.json"
meta_path = os.path.join(metadata_dir, meta_filename)
with open(meta_path, "w", encoding="utf-8") as f:
    json.dump(metadata, f, ensure_ascii=False, indent=2)

print(f"\n✅ Updated {updated_count} statutes in {DB_NAME}.{COLL_NAME} with common fields brought up.")
print(f"📊 Metadata saved to {meta_path}")

client.close()

