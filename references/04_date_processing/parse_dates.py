from pymongo import MongoClient
from tqdm import tqdm
from dateutil import parser
import json
import os
from collections import defaultdict
from datetime import date

MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "Batched-Statutes"
COLL_NAME = "batch3"

client = MongoClient(MONGO_URI)
col = client[DB_NAME][COLL_NAME]

docs = list(col.find({}))
total = len(docs)

# Initial stats
both_filled = 0
only_date = 0
only_prom = 0
both_missing = 0

# Metadata dictionary
metadata = defaultdict(dict)
metadata['db_name'] = DB_NAME
metadata['collection'] = COLL_NAME
metadata['script'] = 'parse_dates.py'
metadata['initial_stats'] = {}
metadata['normalization'] = {}
metadata['post_stats'] = {}
metadata['processing_details'] = {}

def is_filled(val):
    return val is not None and str(val).strip() != ''

for doc in docs:
    date_val = doc.get("Date")
    prom_val = doc.get("Promulgation_Date")
    date_filled = is_filled(date_val)
    prom_filled = is_filled(prom_val)
    if date_filled and prom_filled:
        both_filled += 1
    elif date_filled:
        only_date += 1
    elif prom_filled:
        only_prom += 1
    else:
        both_missing += 1

metadata['initial_stats'] = {
    'total_documents': total,
    'both_fields_filled': both_filled,
    'only_date_filled': only_date,
    'only_promulgation_filled': only_prom,
    'both_missing': both_missing,
}

print("--- Initial Field Stats ---")
print(f"Total documents: {total}")
print(f"Both fields filled: {both_filled} ({both_filled/total*100:.2f}%)")
print(f"Only Date filled: {only_date} ({only_date/total*100:.2f}%)")
print(f"Only Promulgation_Date filled: {only_prom} ({only_prom/total*100:.2f}%)")
print(f"Both fields missing/null: {both_missing} ({both_missing/total*100:.2f}%)")

# Normalize and update
valid_count = 0
missing_count = 0
metadata['normalization']['total_processed'] = total
metadata['normalization']['valid_count'] = 0
metadata['normalization']['missing_count'] = 0

for doc in tqdm(docs, desc="Normalizing Date field"):
    date_str = doc.get("Date") or doc.get("Promulgation_Date")
    norm_date = None
    if is_filled(date_str):
        try:
            dt = parser.parse(date_str, fuzzy=True)
            norm_date = dt.strftime("%d-%b-%Y")
        except Exception:
            norm_date = None
    update = {"$unset": {"Promulgation_Date": ""}}
    if norm_date:
        valid_count += 1
        update["$set"] = {"Date": norm_date}
    else:
        missing_count += 1
        update["$set"] = {"Date": ""}
    col.update_one({"_id": doc["_id"]}, update)

metadata['normalization']['valid_count'] = valid_count
metadata['normalization']['missing_count'] = missing_count

# Post-processing stats
# Only check for 'Date' field now
docs_after = list(col.find({}))
valid_after = 0
missing_after = 0
for doc in docs_after:
    if is_filled(doc.get("Date")):
        valid_after += 1
    else:
        missing_after += 1

metadata['post_stats'] = {
    'valid_normalized_date': valid_after,
    'missing_or_invalid_date': missing_after,
}

print("\n--- After Normalization ---")
print(f"Documents with valid normalized Date: {valid_after} ({valid_after/total*100:.2f}%)")
print(f"Documents missing/invalid Date: {missing_after} ({missing_after/total*100:.2f}%)")

# Save metadata to file

# Add script/db/collection/date info to metadata
metadata['script'] = 'parse_dates.py'
metadata['db_name'] = DB_NAME
metadata['collection'] = COLL_NAME
metadata['date'] = date.today().isoformat()

# Save metadata to metadata/ folder with new naming convention
metadata_dir = "metadata"
os.makedirs(metadata_dir, exist_ok=True)
meta_filename = f"metadata_parse_dates_{DB_NAME}_{COLL_NAME}_{date.today().isoformat()}.json"
meta_path = os.path.join(metadata_dir, meta_filename)
with open(meta_path, "w", encoding="utf-8") as f:
    json.dump(metadata, f, indent=2)
print(f"Metadata saved to {meta_path}")
