#!/usr/bin/env python3
"""
Dry-run field cleaning script for Phase 3 batches.
Runs reference-like cleaning steps on selected batches and reports what WOULD change.

Usage:
  python field_cleaning_dryrun.py --db Batched-Statutes --prefix batch --batches 1 --dry-run
"""
import argparse
import json
from pymongo import MongoClient
from collections import Counter, defaultdict
from datetime import date
import os

from importlib.machinery import SourceFileLoader
import sys
import os

# Load FieldCleaningEngine from backend package so dry-run uses the same logic
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
from app.api.v1.endpoints import phase3

def clean_text_field(text: str) -> str:
    if not text:
        return ""
    cleaned = " ".join(str(text).split())
    cleaned = "".join(c for c in cleaned if c.isalnum() or c.isspace() or c in ".,;:()[]{}'\"-")
    return cleaned.strip()

# Fields the user requested to DROP (cleanup/field-drop policy)
# Keep this list minimal: drop blob/pdf and the RAG/HTML derived fields here.
FIELDS_TO_DROP = {"Blob_Url", "PDF_URL", "Statute_RAG_Content"}
SECTION_FIELDS_TO_DROP = {"Statute_RAG_Content", "Statute_HTML", "PDF_URL", "Blob_Url"}
SECTION_FIELDS = ["Section", "Definition", "Citations", "Statute", "Text", "Title", "Subsection", "Bookmark_ID"]


def find_common_fields(sections):
    if not sections:
        return {}
    common = set(sections[0].keys())
    for s in sections[1:]:
        common &= set(s.keys())
    for k in list(common):
        if k in ("Section", "Content", "_id"):
            common.discard(k)
    res = {}
    for k in common:
        first = sections[0].get(k)
        if all(s.get(k) == first for s in sections):
            res[k] = first
    return res


def is_single_empty_section(sections):
    if not isinstance(sections, list) or len(sections) != 1:
        return False
    sec = sections[0]
    if not isinstance(sec, dict):
        return False
    for v in sec.values():
        if v not in (None, "", [], {}):
            return False
    return True


def apply_cleaning(doc):
    # Return (cleaned_doc_or_None_if_dropped, cleaning_log)
    log = {"dropped": False, "fields_dropped": [], "section_fields_dropped": [], "common_fields_moved": [], "text_fields_cleaned": [], "case": "unknown", "would_be_dropped_by_cleanup": False}
    # Determine case (single-section vs multi-section)
    sections = doc.get("Sections") if isinstance(doc.get("Sections"), list) else []
    if is_single_empty_section(sections):
        log["case"] = "single"
    elif isinstance(sections, list) and len(sections) > 1:
        log["case"] = "multi"
    else:
        log["case"] = "other"

    # Validation - simple Pakistan checks
    preamble = (doc.get("Preamble") or "")
    name = (doc.get("Statute_Name") or "")
    province = doc.get("Province") or ""
    date_str = doc.get("Date") or ""
    is_pak = False
    if isinstance(preamble, str) and "pakistan" in preamble.lower():
        is_pak = True
    if isinstance(name, str) and "pakistan" in name.lower():
        is_pak = True
    if province in ("Azad Kashmir And Jammu", "Balochistan", "Federal", "Khyber Pakhtunkhwa", "Punjab", "Sindh"):
        is_pak = True
    # simplistic date check omitted for dry-run
    if not is_pak:
        # Field-cleaning should not perform dataset-level drops (pre-1947 / non-Pakistan).
        # Those removals belong to the separate cleanup step. Mark the doc and continue.
        log["would_be_dropped_by_cleanup"] = True

    cleaned = doc.copy()
    # Drop top-level fields
    for f in list(FIELDS_TO_DROP):
        if f in cleaned:
            cleaned.pop(f, None)
            log["fields_dropped"].append(f)
    # Normalize top-level text
    for tf in ("Statute_Name", "Preamble"):
        if tf in cleaned and isinstance(cleaned[tf], str):
            cleaned_val = clean_text_field(cleaned[tf])
            if cleaned_val != cleaned[tf]:
                cleaned[tf] = cleaned_val
                log["text_fields_cleaned"].append(tf)
    # Sections
    if isinstance(cleaned.get("Sections"), list):
        secs = cleaned["Sections"]
        # Move only explicit PROMOTE_FIELDS up (user policy)
        PROMOTE_FIELDS = {"Source", "Year", "Promulgation_Date", "Act_Ordinance", "Province", "Date"}
        common = find_common_fields(secs)
        # Only consider promoting fields that are both common and in the PROMOTE_FIELDS set
        promote_keys = [k for k in PROMOTE_FIELDS if k in common]
        for k in promote_keys:
            v = common.get(k)
            # still avoid lifting anything that is explicitly in drop-lists
            if k in FIELDS_TO_DROP or k in SECTION_FIELDS_TO_DROP:
                log.setdefault("common_fields_skipped", []).append(k)
                continue
            if k not in cleaned:
                cleaned[k] = v
                log["common_fields_moved"].append(k)
        # Remove common fields from sections and drop section-level fields
        new_secs = []
        for s in secs:
            s = dict(s)
            for k in common.keys():
                if k in s:
                    s.pop(k, None)
            for sf in SECTION_FIELDS_TO_DROP:
                if sf in s:
                    s.pop(sf, None)
                    if sf not in log["section_fields_dropped"]:
                        log["section_fields_dropped"].append(sf)
            # normalize content-like fields
            for f in ("Content", "Statute", "Text"):
                if f in s and isinstance(s[f], str):
                    cleaned_val = clean_text_field(s[f])
                    if cleaned_val != s[f]:
                        s[f] = cleaned_val
                        log["text_fields_cleaned"].append(f)
            new_secs.append(s)
        cleaned["Sections"] = new_secs
        # Single empty section handling
        if is_single_empty_section(cleaned.get("Sections")):
            new_section = {}
            for field in SECTION_FIELDS:
                if field in cleaned:
                    new_section[field] = cleaned.pop(field)
            # Also remove section-only top-level fields
            for tf in SECTION_FIELDS_TO_DROP:
                if tf in cleaned:
                    cleaned.pop(tf, None)
                    if tf not in log["fields_dropped"]:
                        log["fields_dropped"].append(tf)
            if "Citations" in new_section and new_section.get("Citations") is None:
                new_section["Citations"] = []
            if "Section" not in new_section:
                new_section["Section"] = "Preamble"
            cleaned["Sections"] = [new_section]
    # Record case explicitly in returned log
    return cleaned, log


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="Batched-Statutes")
    parser.add_argument("--prefix", default="batch_")
    parser.add_argument("--batches", nargs="*", type=int, default=[1])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--full", action="store_true", help="Run on the full collection (no safety limit).")
    args = parser.parse_args()

    client = MongoClient('mongodb://localhost:27017')
    target_db = client[args.db]

    batches = [f"{args.prefix}{n}" for n in args.batches]

    overall = {
        "processed": 0,
        "dropped": 0,
        "would_update": 0,
    "would_be_dropped_by_cleanup": 0,
        "fields_dropped_count": Counter(),
        "section_fields_dropped_count": Counter(),
        "common_fields_moved_count": Counter(),
        "text_fields_cleaned_count": Counter(),
        "sample_changes": [],
        "by_case": {
            "single": {"processed": 0, "dropped": 0, "would_update": 0},
            "multi": {"processed": 0, "dropped": 0, "would_update": 0},
            "other": {"processed": 0, "dropped": 0, "would_update": 0}
        }
    }

    for batch in batches:
        coll = target_db[batch]
        # default safety limit (200) to avoid accidental full runs; allow --full to override
        if args.full:
            docs = list(coll.find())
        else:
            docs = list(coll.find().limit(200))  # limit for dry-run safety
        print(f"Processing {len(docs)} docs from {batch} (dry-run={args.dry_run})")
        for doc in docs:
            overall["processed"] += 1
            # Use FieldCleaningEngine.clean_document_structure to exercise the same code path
            try:
                cleaned = phase3.FieldCleaningEngine.clean_document_structure(doc.copy())
                # apply_cleaning returns (cleaned_doc, log) in original helper; we build a log placeholder
                log = {"dropped": False, "fields_dropped": [], "section_fields_dropped": [], "common_fields_moved": [], "text_fields_cleaned": [], "case": "unknown", "would_be_dropped_by_cleanup": False}
            except Exception:
                # fallback to local apply_cleaning logic if centralized engine fails
                cleaned, log = apply_cleaning(doc)

            # Update per-case processed
            case = log.get("case", "other")
            overall["by_case"].setdefault(case, {"processed": 0, "dropped": 0, "would_update": 0})
            overall["by_case"][case]["processed"] += 1

            if cleaned is None:
                overall["dropped"] += 1
                overall["by_case"][case]["dropped"] += 1
                overall["sample_changes"].append({"_id": str(doc.get("_id")), "action": "would_drop", "case": case})
                continue

            # If this doc was flagged for cleanup (non-Pakistan/pre-1947), record it but do not drop here
            if log.get("would_be_dropped_by_cleanup"):
                overall["would_be_dropped_by_cleanup"] += 1
                if len(overall["sample_changes"]) < 50:
                    overall["sample_changes"].append({"_id": str(doc.get("_id")), "action": "would_be_dropped_by_cleanup", "case": case, "log": log})

            # compare
            if cleaned != doc:
                overall["would_update"] += 1
                overall["by_case"][case]["would_update"] += 1
                overall["sample_changes"].append({"_id": str(doc.get("_id")), "action": "would_update", "log": log, "case": case})
                for f in log.get("fields_dropped", []):
                    overall["fields_dropped_count"][f] += 1
                for f in log.get("section_fields_dropped", []):
                    overall["section_fields_dropped_count"][f] += 1
                for f in log.get("common_fields_moved", []):
                    overall["common_fields_moved_count"][f] += 1
                for f in log.get("text_fields_cleaned", []):
                    overall["text_fields_cleaned_count"][f] += 1
            else:
                # unchanged
                pass

    # write metadata
    metadata_dir = os.path.join(os.path.dirname(__file__), '../app/api/v1/endpoints/../../metadata')
    os.makedirs(metadata_dir, exist_ok=True)
    meta = {
        "script": "field_cleaning_dryrun.py",
        "date": date.today().isoformat(),
        "db": args.db,
        "batches": batches,
        "results": {
            "processed": overall["processed"],
            "dropped": overall["dropped"],
            "would_update": overall["would_update"],
            "would_be_dropped_by_cleanup": overall.get("would_be_dropped_by_cleanup", 0),
            "fields_dropped_count": dict(overall["fields_dropped_count"]),
            "section_fields_dropped_count": dict(overall["section_fields_dropped_count"]),
            "common_fields_moved_count": dict(overall["common_fields_moved_count"]),
            "text_fields_cleaned_count": dict(overall["text_fields_cleaned_count"]),
            "sample_changes": overall["sample_changes"]
        }
    }
    meta_path = os.path.join(metadata_dir, f"metadata_field_cleaning_dryrun_{args.db}_{batches[0]}_{date.today().isoformat()}.json")
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(json.dumps({"processed": overall["processed"], "dropped": overall["dropped"], "would_update": overall["would_update"]}, indent=2))
    print(f"Metadata written to: {meta_path}")


if __name__ == '__main__':
    main()
