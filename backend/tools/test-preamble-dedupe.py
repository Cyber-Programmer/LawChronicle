#!/usr/bin/env python3
"""Test helper: load remove_preamble_duplicates from phase3.py and apply to a sample doc.

Usage: python test_preamble_dedupe.py
"""
import sys
from importlib.machinery import SourceFileLoader
from pymongo import MongoClient
import json
import os

# Ensure project root is on sys.path so package relative imports resolve
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.api.v1.endpoints import phase3

FieldCleaningEngine = getattr(phase3, 'FieldCleaningEngine', None)
if not FieldCleaningEngine:
    print('FieldCleaningEngine not found in phase3.py')
    raise SystemExit(1)

fn = getattr(FieldCleaningEngine, 'remove_preamble_duplicates', None)
if not fn:
    print('remove_preamble_duplicates not found in phase3.py')
    raise SystemExit(1)

client = MongoClient('mongodb://localhost:27017')
db = client['Batched-Statutes']
coll = db['batch_3']

doc = coll.find_one()  # grab any sample doc
if not doc:
    print('No documents found in batch_3')
    raise SystemExit(1)

print('Document _id:', str(doc.get('_id')))
print('Original Sections count:', len(doc.get('Sections', [])))
print('First section name:', (doc.get('Sections') or [{}])[0].get('Section'))
print('\n--- Original first section content (truncated 400 chars) ---')
first_content = (doc.get('Sections') or [{}])[0].get('Content') or (doc.get('Sections') or [{}])[0].get('Statute') or doc.get('Preamble') or ''
print(first_content[:400])

new = fn(doc.copy())
print('\n--- After remove_preamble_duplicates ---')
print('New Sections count:', len(new.get('Sections', [])))
print('First section name:', (new.get('Sections') or [{}])[0].get('Section'))
print('\n--- New first section content (truncated 400 chars) ---')
first_content_new = (new.get('Sections') or [{}])[0].get('Content') or (new.get('Sections') or [{}])[0].get('Statute') or new.get('Preamble') or ''
print(first_content_new[:400])

print('\n--- Sections overview after dedupe ---')
for i, s in enumerate(new.get('Sections', [])):
    sec_name = s.get('Section')
    content = (s.get('Content') or s.get('Statute') or s.get('Definition') or '')
    print(f"{i}: {sec_name} (len={len(content)})")

print('\nPrinted truncated outputs.')
