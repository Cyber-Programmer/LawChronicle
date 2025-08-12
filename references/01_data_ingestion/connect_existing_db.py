from pymongo import MongoClient
from tqdm import tqdm
from collections import defaultdict, Counter
import os
from datetime import datetime
import json

# --- CONFIG ---
DB_NAME = "Statutes"
COLLECTION_NAME = "raw_statutes"
MONGO_URI = "mongodb://localhost:27017"
SAMPLE_SIZE = 3

# --- Metadata setup ---
from datetime import date
metadata = {
    "script": "connect_existing_db.py",
    "db_name": DB_NAME,
    "collection": COLLECTION_NAME,
    "date": date.today().isoformat(),
    "total_documents": 0,
    "total_fields": 0,
    "fields_with_90pct_null_or_missing": 0,
    "unique_statute_names": 0,
    "sample_statute_names": [],
    "field_stats": {},
    "summary": "Scans all documents in the raw statute DB, collects field stats, and logs summary."
}

# Setup logging
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_filename = f"db_scan_{timestamp}.log"
log_path = os.path.join(log_dir, log_filename)

# Configure logging
# Remove: logging.basicConfig(
# Remove:     level=logging.INFO,
# Remove:     format='%(asctime)s - %(levelname)s - %(message)s',
# Remove:     handlers=[
# Remove:         logging.FileHandler(log_path),
# Remove:         logging.StreamHandler()  # Also print to console
# Remove:     ]
# Remove: )

# Remove: logger = logging.getLogger(__name__)

# Connect to MongoDB
client = MongoClient(MONGO_URI)
collection = client[DB_NAME][COLLECTION_NAME]

field_stats = defaultdict(lambda: {"null": 0, "missing": 0, "non_null": 0})
sample_values = defaultdict(list)
unique_statute_names = set()
total_docs = collection.count_documents({})
metadata["total_documents"] = total_docs

print(f"🔍 Scanning {total_docs} documents from {DB_NAME}.{COLLECTION_NAME}...")

for doc in tqdm(collection.find({}, projection=None), total=total_docs):
    keys = set(doc.keys())
    # Track unique statute names
    if "Statute_Name" in doc and doc["Statute_Name"]:
        unique_statute_names.add(doc["Statute_Name"])
    # Count missing for all seen fields
    for field in field_stats:
        if field not in keys:
            field_stats[field]["missing"] += 1
    # Count null/non-null and collect samples
    for field in keys:
        if doc[field] is None or doc[field] == "":
            field_stats[field]["null"] += 1
        else:
            field_stats[field]["non_null"] += 1
        if len(sample_values[field]) < SAMPLE_SIZE:
            sample_values[field].append(doc[field])
        # Ensure field is initialized even if never seen before
        _ = field_stats[field]

print("\n📋 Field Statistics (All Fields):\n")
print(f"{'Field Name':<25} {'Null %':<8} {'Missing %':<10} {'Non-Null %':<12} {'Counts'}")
print("-" * 70)

# Sort fields by null+missing percentage (highest first)
sorted_fields = sorted(field_stats.items(), key=lambda x: (x[1]["null"] + x[1]["missing"]) / total_docs, reverse=True)

for field, counts in sorted_fields:
    null_percentage = (counts["null"] / total_docs) * 100
    missing_percentage = (counts["missing"] / total_docs) * 100
    non_null_percentage = (counts["non_null"] / total_docs) * 100
    counts_str = f"{counts['null']}/{counts['missing']}/{counts['non_null']}"
    print(f"{field:<25} {null_percentage:>6.1f}% {missing_percentage:>8.1f}% {non_null_percentage:>10.1f}% {counts_str}")
    print(f"    Sample values: {sample_values[field]}")

print(f"\n📊 Summary:")
print(f"   - Total documents: {total_docs}")
print(f"   - Total fields found: {len(field_stats)}")
print(f"   - Fields with 90%+ null/missing: {sum(1 for _, counts in field_stats.items() if (counts['null'] + counts['missing']) / total_docs >= 0.9)}")
print(f"   - Unique Statute_Name count: {len(unique_statute_names)}")
print(f"   - Sample Statute_Name values: {list(unique_statute_names)[:5]}")
print(f"   - Log file saved to: {log_path}")

metadata["total_fields"] = len(field_stats)
metadata["fields_with_90pct_null_or_missing"] = sum(1 for _, counts in field_stats.items() if (counts["null"] + counts["missing"]) / total_docs >= 0.9)
metadata["unique_statute_names"] = len(unique_statute_names)
metadata["sample_statute_names"] = list(unique_statute_names)[:5]
metadata["field_stats"] = {field: dict(counts) for field, counts in field_stats.items()}

# Save metadata to file
metadata_dir = "metadata"
os.makedirs(metadata_dir, exist_ok=True)
meta_filename = f"metadata_connect_existing_db_{DB_NAME}_{COLLECTION_NAME}_{date.today().isoformat()}.json"
meta_path = os.path.join(metadata_dir, meta_filename)
with open(meta_path, "w", encoding="utf-8") as f:
    json.dump(metadata, f, indent=2)
print(f"Metadata saved to {meta_path}")