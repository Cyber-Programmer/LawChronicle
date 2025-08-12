from pymongo import MongoClient
import json
from tqdm import tqdm
from datetime import date
import os

# --- CONFIG ---
MONGO_URI = "mongodb://localhost:27017"
CLEAN_DB = "Statutes"
CLEAN_COLL = "normalized_statutes"
INPUT_JSON = "02_db_normalization/normalized_statutes.json"

client = MongoClient(MONGO_URI)
clean_col = client[CLEAN_DB][CLEAN_COLL]

# --- Metadata setup ---
metadata = {
    "script": "create_clean_db.py",
    "db_name": CLEAN_DB,
    "collection": CLEAN_COLL,
    "date": date.today().isoformat(),
    "input_json": INPUT_JSON,
    "total_statutes": 0,
    "summary": "Loads normalized statutes from JSON, normalizes names, sorts, and inserts into MongoDB."
}

# Load JSON
with open(INPUT_JSON, "r", encoding="utf-8") as f:
    statutes = json.load(f)
metadata["total_statutes"] = len(statutes)

# Normalize statute names: if all uppercase, convert to title case
for statute in tqdm(statutes, desc="Normalizing statute names"):
    # Try both "name" and "Statute_Name" for compatibility
    if "name" in statute:
        name = statute["name"]
        if isinstance(name, str) and name.isupper():
            statute["name"] = name.title()
    elif "Statute_Name" in statute:
        name = statute["Statute_Name"]
        if isinstance(name, str) and name.isupper():
            statute["Statute_Name"] = name.title()

# Sort statutes alphabetically by name (prefer "name", fallback to "Statute_Name")
def get_statute_name(statute):
    return statute.get("name") or statute.get("Statute_Name") or ""

statutes.sort(key=get_statute_name)

# Insert into MongoDB
clean_col.delete_many({})  # Clear target collection first
clean_col.insert_many(statutes)

# Save metadata to file
metadata_dir = "metadata"
os.makedirs(metadata_dir, exist_ok=True)
meta_filename = f"metadata_create_clean_db_{CLEAN_DB}_{CLEAN_COLL}_{date.today().isoformat()}.json"
meta_path = os.path.join(metadata_dir, meta_filename)
with open(meta_path, "w", encoding="utf-8") as f:
    json.dump(metadata, f, indent=2)
print(f"Metadata saved to {meta_path}")

print(f"✅ Inserted {len(statutes)} statutes into {CLEAN_DB}.{CLEAN_COLL}")