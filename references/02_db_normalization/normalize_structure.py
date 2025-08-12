from pymongo import MongoClient
from collections import defaultdict
import json
from tqdm import tqdm
import re
import os
import numpy as np
from datetime import datetime, date

# --- CONFIG ---
MONGO_URI = "mongodb://localhost:27017"
RAW_DB = "Statutes"
RAW_COLL = "raw_statutes"
NORMALIZED_DB = "Statutes"
NORMALIZED_COLL = "normalized_statutes"

def normalize_statute_name(name):
    """
    Normalize statute names by:
    - Removing extra whitespace
    - Converting to title case
    - Removing special characters
    - Standardizing common abbreviations
    """
    if not name:
        return "UNKNOWN"
    
    # Convert to string and strip whitespace
    name = str(name).strip()
    
    # Remove extra whitespace and newlines
    name = re.sub(r'\s+', ' ', name)
    
    # Convert to title case
    name = name.title()
    
    # Standardize common abbreviations
    name = name.replace('Act', 'Act')
    name = name.replace('Regulation', 'Regulation')
    name = name.replace('Ordinance', 'Ordinance')
    name = name.replace('Code', 'Code')
    name = name.replace('Law', 'Law')
    
    # Remove special characters but keep spaces and basic punctuation
    name = re.sub(r'[^\w\s\-\.\(\)]', '', name)
    
    # Clean up multiple spaces again
    name = re.sub(r'\s+', ' ', name).strip()
    
    return name if name else "UNKNOWN"

def section_sort_key(section):
    """
    Returns a tuple for sorting using numpy for faster operations:
    - (0, '') for preamble (always first)
    - (1, numeric value) for numeric sections
    - (2, lowercase text) for non-numeric sections
    """
    num = section.get("number", "")
    if isinstance(num, str) and np.char.equal(num.strip().lower(), "preamble"):
        return (0, "")
    
    # Try to parse as int or float using numpy operations
    try:
        # Remove leading/trailing whitespace
        num_str = num.strip() if isinstance(num, str) else str(num)
        
        # Use numpy for faster numeric conversion
        if np.char.isdigit(num_str):
            n = int(num_str)
            return (1, n)
        elif np.char.isnumeric(num_str):
            n = float(num_str)
            return (1, n)
    except (ValueError, TypeError):
        pass
    
    # Not numeric, not preamble - use numpy for faster string operations
    return (2, np.char.lower(str(num) if num else ""))

# Initialize metadata tracking
metadata = {
    "total_documents_processed": 0,
    "unique_statutes": 0,
    "total_sections": 0,
    "sections_by_type": {
        "preamble": 0,
        "numeric": 0,
        "non_numeric": 0
    },
    "sorting_decisions": {
        "alphabetical_sort": 0,
        "numeric_sort": 0
    },
    "statute_details": [],
    "normalized_names": {}
}

print("🔍 Starting database normalization process...")
print(f"📊 Source: {RAW_DB}.{RAW_COLL}")
print(f"📊 Target: {NORMALIZED_DB}.{NORMALIZED_COLL}")

# Connect to MongoDB
client = MongoClient(MONGO_URI)
raw_col = client[RAW_DB][RAW_COLL]
normalized_db = client[NORMALIZED_DB]
normalized_col = normalized_db[NORMALIZED_COLL]

# Clear existing normalized data
normalized_col.drop()
print("🗑️  Cleared existing normalized collection")

# Group sections by normalized Statute_Name
statute_dict = defaultdict(list)
for doc in tqdm(raw_col.find({}, projection=None), desc="Processing documents"):
    metadata["total_documents_processed"] += 1
    original_name = doc.get("Statute_Name", "UNKNOWN")
    normalized_name = normalize_statute_name(original_name)
    
    # Track name normalization
    if original_name != normalized_name:
        metadata["normalized_names"][original_name] = normalized_name
    
    # Remove fields you don't want in the section
    section = {k: v for k, v in doc.items() if k not in ["Statute_Name", "_id"]}
    statute_dict[normalized_name].append(section)

print(f"📋 Processed {metadata['total_documents_processed']} documents")
print(f"📋 Found {len(statute_dict)} unique statutes")

# Build normalized list and insert into MongoDB
normalized_docs = []
for statute_name, sections in statute_dict.items():
    metadata["unique_statutes"] += 1
    metadata["total_sections"] += len(sections)
    
    # Track section types
    for section in sections:
        num = section.get("number", "")
        if isinstance(num, str) and num.strip().lower() == "preamble":
            metadata["sections_by_type"]["preamble"] += 1
        else:
            try:
                float(num)
                metadata["sections_by_type"]["numeric"] += 1
            except (ValueError, TypeError):
                metadata["sections_by_type"]["non_numeric"] += 1
    
    statute_detail = {
        "statute_name": statute_name,
        "section_count": len(sections),
        "section_numbers": [s.get("number", "") for s in sections],
        "sorting_method": "unknown"
    }
    
    # If only 1 or 2 sections and both are non-numeric, sort alphabetically (but preamble always first)
    if len(sections) <= 2:
        # Check if all section numbers are non-numeric (except preamble)
        non_numeric = []
        for s in sections:
            num = s.get("number", "")
            if isinstance(num, str) and num.strip().lower() == "preamble":
                continue
            try:
                float(num)
            except (ValueError, TypeError):
                non_numeric.append(s)
        # If all non-preamble sections are non-numeric, sort alphabetically (preamble first)
        if len(non_numeric) == (len(sections) - sum(1 for s in sections if isinstance(s.get("number", ""), str) and s.get("number", "").strip().lower() == "preamble")):
            sections = sorted(sections, key=section_sort_key)
            metadata["sorting_decisions"]["alphabetical_sort"] += 1
            statute_detail["sorting_method"] = "alphabetical"
        else:
            sections = sorted(sections, key=section_sort_key)
            metadata["sorting_decisions"]["numeric_sort"] += 1
            statute_detail["sorting_method"] = "numeric"
    else:
        # For more than 2 sections, always use the sort key (preamble first, then numeric, then text)
        sections = sorted(sections, key=section_sort_key)
        metadata["sorting_decisions"]["numeric_sort"] += 1
        statute_detail["sorting_method"] = "numeric"
    
    metadata["statute_details"].append(statute_detail)
    
    normalized_docs.append({
        "Statute_Name": statute_name,
        "Sections": sections
    })

# Sort statutes alphabetically by name
normalized_docs.sort(key=lambda x: x["Statute_Name"].lower())

# Insert into MongoDB
if normalized_docs:
    normalized_col.insert_many(normalized_docs)
    print(f"✅ Inserted {len(normalized_docs)} normalized statutes into {NORMALIZED_DB}.{NORMALIZED_COLL}")

# Create index on Statute_Name for faster queries
normalized_col.create_index("Statute_Name")
print("📊 Created index on Statute_Name field")

# Log comprehensive metadata
print("\n📊 NORMALIZATION METADATA:")
print("=" * 50)
print(f"📋 Total documents processed: {metadata['total_documents_processed']}")
print(f"📋 Unique statutes: {metadata['unique_statutes']}")
print(f"📋 Total sections: {metadata['total_sections']}")
print(f"📋 Average sections per statute: {metadata['total_sections'] / metadata['unique_statutes']:.2f}")

print("\n📊 Section Types:")
print(f"   - Preamble sections: {metadata['sections_by_type']['preamble']}")
print(f"   - Numeric sections: {metadata['sections_by_type']['numeric']}")
print(f"   - Non-numeric sections: {metadata['sections_by_type']['non_numeric']}")

print("\n📊 Sorting Decisions:")
print(f"   - Alphabetical sorting: {metadata['sorting_decisions']['alphabetical_sort']} statutes")
print(f"   - Numeric sorting: {metadata['sorting_decisions']['numeric_sort']} statutes")

print(f"\n📊 Name Normalizations: {len(metadata['normalized_names'])}")
if metadata['normalized_names']:
    print("   Sample normalizations:")
    for i, (original, normalized) in enumerate(list(metadata['normalized_names'].items())[:5]):
        print(f"     '{original}' → '{normalized}'")

# Add script/db/collection/date info to metadata
metadata["script"] = "normalize_structure.py"
metadata["db_name"] = NORMALIZED_DB
metadata["collection"] = NORMALIZED_COLL
metadata["date"] = date.today().isoformat()

# Save metadata to metadata/ folder with new naming convention
metadata_dir = "metadata"
os.makedirs(metadata_dir, exist_ok=True)
meta_filename = f"metadata_normalize_structure_{NORMALIZED_DB}_{NORMALIZED_COLL}_{date.today().isoformat()}.json"
meta_path = os.path.join(metadata_dir, meta_filename)
with open(meta_path, "w", encoding="utf-8") as f:
    json.dump(metadata, f, ensure_ascii=False, indent=2)

print(f"\n✅ Normalized statutes saved to {NORMALIZED_DB}.{NORMALIZED_COLL}")
print(f"📊 Metadata saved to {meta_path}")

client.close()