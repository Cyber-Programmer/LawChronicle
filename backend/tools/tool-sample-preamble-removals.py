#!/usr/bin/env python3
"""Sample preamble fragment removal reporter.
Fetches N documents from a batch, runs FieldCleaningEngine.clean_document_structure, and prints removals.
Usage: python sample_preamble_removals.py [batch_name] [limit]
"""
import sys
import json
from pymongo import MongoClient
import os
import sys

# ensure backend package importable
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.api.v1.endpoints import phase3


def main():
    batch = sys.argv[1] if len(sys.argv) > 1 else 'batch_3'
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 25

    client = MongoClient('mongodb://localhost:27017')
    db = client['Batched-Statutes']
    coll = db[batch]

    docs = list(coll.find().limit(limit))
    report = []
    for doc in docs:
        cleaned = phase3.FieldCleaningEngine.clean_document_structure(doc.copy())
        removals = cleaned.get('_preamble_fragment_removals') or []
        if removals:
            for rem in removals:
                sec_idx = rem.get('section_index')
                for entry in rem.get('removed', []):
                    report.append({
                        'doc_id': str(doc.get('_id')),
                        'section_index': sec_idx,
                        'field': entry.get('field'),
                        'fragment': entry.get('fragment')
                    })

    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
