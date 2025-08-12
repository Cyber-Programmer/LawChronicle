from pymongo import MongoClient
client = MongoClient('mongodb://localhost:27017/')
batched_db = client['Batched-Statutes']

print('Restored section splitting collections:')
for coll_name in ['batch_1', 'batch_2', 'batch_3']:
    count = batched_db[coll_name].count_documents({})
    print(f'  {coll_name}: {count} documents')

print('\nSample document from batch_1 (checking fields):')
doc = batched_db['batch_1'].find_one({}, {'_id': 1, 'Statute_Name': 1, 'Source': 1, 'PDF_URL': 1, 'Sections': 1})
print(f'  Has Source field: {"Source" in doc}')
print(f'  Has PDF_URL field: {"PDF_URL" in doc}')
if 'Sections' in doc and doc['Sections']:
    print(f'  Number of sections: {len(doc["Sections"])}')
    if doc['Sections']:
        section = doc['Sections'][0]
        print(f'  Section has these fields: {list(section.keys())}')
