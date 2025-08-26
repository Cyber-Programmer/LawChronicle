# Quick check for Gilgit/Baltistan province validation
from pymongo import MongoClient
from app.api.v1.endpoints import phase3

MONGO = 'mongodb://localhost:27017'
DB = 'Batched-Statutes'

client = MongoClient(MONGO)
db = client[DB]

collections = [c for c in db.list_collection_names() if c.startswith('batch')]
report = []

for coll_name in collections:
    coll = db[coll_name]
    cursor = coll.find({'Province': {'$regex': '(?i)gilgit|baltistan'}}).limit(10)
    matched = 0
    validated = 0
    samples = []
    for doc in cursor:
        matched += 1
        try:
            is_pk = phase3.FieldCleaningEngine.validate_pakistan_law(doc)
        except Exception as e:
            is_pk = f'error: {str(e)}'
        if is_pk is True:
            validated += 1
        if len(samples) < 5:
            samples.append({'_id': str(doc.get('_id')), 'Province': doc.get('Province'), 'Statute_Name': (doc.get('Statute_Name') or '')[:120], 'validated': is_pk})
    if matched > 0:
        report.append({'collection': coll_name, 'matched': matched, 'validated': validated, 'samples': samples})

if not report:
    print('No Gilgit/Baltistan matches found in Batched-Statutes (prefix batch_)')
else:
    for r in report:
        print(f"{r['collection']}: matched={r['matched']}, validated={r['validated']}")
        for s in r['samples']:
            print('  ', s)
