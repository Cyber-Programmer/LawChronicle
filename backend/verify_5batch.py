from pymongo import MongoClient

# Verify the results
client = MongoClient('mongodb://localhost:27017/')
batched_db = client['Batched-Statutes']

print('Verification of 5-batch field cleaning:')
total_docs = 0
for i in range(1, 6):
    coll_name = f'test_batch_{i}'
    count = batched_db[coll_name].count_documents({})
    total_docs += count
    print(f'  {coll_name}: {count} documents')

print(f'  Total across all 5 batches: {total_docs} documents')

# Check a sample document to verify field cleaning
print('\nSample document from test_batch_1 (after cleaning):')
doc = batched_db['test_batch_1'].find_one({}, {'_id': 1, 'Statute_Name': 1, 'field_cleaned_at': 1, 'field_cleaning_log': 1})
print(f'  Has cleaning timestamp: {"field_cleaned_at" in doc}')
print(f'  Has cleaning log: {"field_cleaning_log" in doc}')
if 'field_cleaning_log' in doc:
    log = doc['field_cleaning_log']
    print(f'  Fields moved up: {len(log.get("common_fields_moved_up", []))}')
    print(f'  Section fields dropped: {log.get("section_fields_dropped", [])}')
