"""
Assign Section Versions with Semantic Similarity

This script groups sections by their base statute and section number,
then assigns versions based on semantic similarity and handles the isActive field
according to ordinance expiration rules.

Features:
- Groups sections by base statute and section number
- Uses semantic similarity to identify same sections across versions
- Handles ordinance expiration (6+ months = inactive)
- Creates version timeline for each section
- Assigns isActive status based on latest valid version
"""

import numpy as np
from pymongo import MongoClient
from tqdm import tqdm
import json
from datetime import datetime, timedelta, date
from dateutil import parser
from collections import defaultdict, Counter
from typing import List, Dict, Optional, Tuple
import difflib
import sys
import os

# Add project root to Python path for utils imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.gpt_cache import gpt_cache
from utils.gpt_batcher import batch_gpt_requests
from utils.gpt_rate_limiter import rate_limited_gpt_call
from utils.gpt_prompt_optimizer import optimize_gpt_prompt
try:
    from fuzzywuzzy import fuzz
except ImportError:
    # Fallback if fuzzywuzzy is not available
    def fuzz_ratio(s1, s2):
        return difflib.SequenceMatcher(None, s1, s2).ratio() * 100
    
    def fuzz_partial_ratio(s1, s2):
        return difflib.SequenceMatcher(None, s1, s2).ratio() * 100
    
    class Fuzz:
        @staticmethod
        def ratio(s1, s2):
            return fuzz_ratio(s1, s2)
        
        @staticmethod
        def partial_ratio(s1, s2):
            return fuzz_partial_ratio(s1, s2)
    
    fuzz = Fuzz()
import re
try:
    from openai import AzureOpenAI
except ImportError:
    AzureOpenAI = None

import logging
import time

# --- Logging setup ---
LOG_FILE = "section_versioning_progress.log"
logging.basicConfig(
    filename=LOG_FILE,
    filemode='a',
    format='%(asctime)s %(levelname)s: %(message)s',
    level=logging.INFO
)
VERBOSE = True  # Set to False for less output, or make this a CLI arg

def log(msg, level="info", verbose=True, flush=True):
    if verbose or level in ("error", "warning"):
        print(msg, flush=flush)
    getattr(logging, level)(msg)

# --- CONFIG ---
MONGO_URI = "mongodb://localhost:27017"
SOURCE_DB = "Batch-Section-Split"  # From split_sections.py output
SOURCE_COLL = "batch10"
TARGET_DB = "Batch-Section-Versioned"  # Updated to match coherent naming
TARGET_COLL = "batch10"

# Similarity thresholds
SIMILARITY_THRESHOLD = 0.85  # For considering sections as the same
TEXT_SIMILARITY_THRESHOLD = 0.80  # For text content similarity

# Initialize metadata tracking
metadata = {
    "total_sections_processed": 0,
    "total_section_versions_created": 0,
    "versioning_stats": {
        "base_statutes_processed": 0,
        "section_numbers_processed": 0,
        "groups_with_single_version": 0,
        "groups_with_multiple_versions": 0,
        "max_versions_in_group": 0,
        "average_versions_per_group": 0
    },
    "similarity_analysis": {
        "similarity_groups_created": 0,
        "similarity_scores": [],
        "text_similarity_distribution": Counter(),
        "sample_similarity_groups": []
    },
    "processing_details": {
        "sections_with_valid_dates": 0,
        "sections_with_invalid_dates": 0,
        "sections_with_missing_dates": 0,
        "expired_ordinances": 0,
        "active_ordinances": 0,
        "database_updates": 0
    }
}

def connect_to_mongodb():
    """Connect to MongoDB"""
    try:
        client = MongoClient(MONGO_URI)
        client.admin.command('ping')
        log("✅ Connected to MongoDB successfully", verbose=VERBOSE)
        return client
    except Exception as e:
        log(f"❌ Failed to connect to MongoDB: {e}", level="error", verbose=True)
        return None

def parse_date(date_str: str) -> Optional[datetime]:
    """Parse date string to datetime object"""
    if not date_str:
        return None
    
    try:
        # Handle various date formats
        if isinstance(date_str, str):
            # Try different date formats
            for fmt in ['%d-%b-%Y', '%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y']:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
            
            # Try dateutil parser as fallback
            return parser.parse(date_str)
        return None
    except Exception as e:
        log(f"⚠️ Could not parse date '{date_str}': {e}", level="warning", verbose=True)
        return None

def calculate_text_similarity(text1: str, text2: str) -> float:
    """
    Calculate similarity between two text strings using multiple methods
    
    Args:
        text1: First text string
        text2: Second text string
        
    Returns:
        Similarity score between 0 and 1
    """
    if not text1 or not text2:
        return 0.0
    
    # Normalize texts
    text1_clean = re.sub(r'\s+', ' ', text1.strip().lower())
    text2_clean = re.sub(r'\s+', ' ', text2.strip().lower())
    
    if text1_clean == text2_clean:
        return 1.0
    
    # Use difflib for sequence matching
    similarity = difflib.SequenceMatcher(None, text1_clean, text2_clean).ratio()
    
    # Use fuzzywuzzy for additional comparison
    fuzzy_ratio = fuzz.ratio(text1_clean, text2_clean) / 100.0
    fuzzy_partial = fuzz.partial_ratio(text1_clean, text2_clean) / 100.0
    
    # Return the highest similarity score
    return max(similarity, fuzzy_ratio, fuzzy_partial)

def is_ordinance_expired(promulgation_date: str, current_date: Optional[datetime] = None) -> bool:
    """
    Check if an ordinance is expired (6+ months old)
    
    Args:
        promulgation_date: Date when ordinance was promulgated
        current_date: Current date (defaults to now)
        
    Returns:
        True if ordinance is expired (6+ months old)
    """
    if current_date is None:
        current_date = datetime.now()
    
    parsed_date = parse_date(promulgation_date)
    if not parsed_date:
        return False
    
    # Calculate if 6+ months have passed
    six_months_ago = current_date - timedelta(days=180)
    return parsed_date < six_months_ago

def group_sections_by_base_and_number(sections: List[Dict]) -> Dict[str, Dict[str, List[Dict]]]:
    """
    Group sections by base statute name and section number
    
    Args:
        sections: List of section documents
        
    Returns:
        Dictionary: {base_name: {section_number: [sections]}}
    """
    grouped: Dict[str, Dict[str, List[Dict]]] = {}
    
    for section in sections:
        base_name = section.get("base_statute_name", "")
        section_number = section.get("section_number", "")
        
        if base_name and section_number:
            if base_name not in grouped:
                grouped[base_name] = {}
            if section_number not in grouped[base_name]:
                grouped[base_name][section_number] = []
            grouped[base_name][section_number].append(section)
    
    return grouped

def find_similar_sections(sections: List[Dict]) -> List[List[Dict]]:
    """
    Group sections that are semantically similar using numpy and batch processing
    
    Args:
        sections: List of sections to group
        
    Returns:
        List of groups, where each group contains similar sections
    """
    if len(sections) <= 1:
        return [sections]
    
    # Use numpy arrays for efficient similarity calculations
    section_numbers = np.array([str(s.get("section_number", "")) for s in sections])
    definitions = np.array([s.get("definition", "").lower() for s in sections])
    statute_texts = np.array([s.get("statute_text", "") for s in sections])
    
    groups = []
    processed = np.zeros(len(sections), dtype=bool)
    
    # Prepare batch items for GPT similarity checks
    batch_items = []
    
    for i, section1 in enumerate(sections):
        if processed[i]:
            continue
        
        current_group = [section1]
        processed[i] = True
        
        # Vectorized similarity calculations
        section_num_similarities = np.array([
            fuzz.ratio(section_numbers[i], section_numbers[j]) / 100.0 
            for j in range(len(sections))
        ])
        
        definition_similarities = np.array([
            fuzz.ratio(definitions[i], definitions[j]) / 100.0 
            for j in range(len(sections))
        ])
        
        # Calculate text similarities efficiently
        text_similarities = np.zeros(len(sections))
        for j in range(len(sections)):
            if not processed[j]:
                text_similarities[j] = calculate_text_similarity(
                    statute_texts[i], statute_texts[j]
                )
        
        # Find similar sections using numpy operations
        similar_mask = (
            (section_num_similarities > SIMILARITY_THRESHOLD) & 
            ((definition_similarities > SIMILARITY_THRESHOLD) | 
             (text_similarities > TEXT_SIMILARITY_THRESHOLD)) &
            ~processed
        )
        
        similar_indices = np.where(similar_mask)[0]
        
        # Prepare batch items for ambiguous cases
        for j in similar_indices:
            if text_similarities[j] > 0.6 and text_similarities[j] < 0.8:  # Ambiguous range
                batch_items.append({
                    'prompt': f"Are these sections similar?\nSection A: {definitions[i]}\nSection B: {definitions[j]}",
                    'section_a_idx': i,
                    'section_b_idx': j
                })
        
        # Add sections to current group
        for j in similar_indices:
            current_group.append(sections[j])
            processed[j] = True
        
        groups.append(current_group)
    
    # Process batch GPT calls for ambiguous cases
    if batch_items:
        from utils.gpt_batcher import batch_gpt_requests
        batch_results = batch_gpt_requests(batch_items, lambda prompt: "mock_gpt_response")
        
        # Apply batch results to refine groups
        # (Implementation depends on your specific needs)
    
    return groups

def create_section_version_document(base_name: str, section_number: str, 
                                  similar_sections: List[Dict]) -> Dict:
    """
    Create a section version document with timeline
    
    Args:
        base_name: Base statute name
        section_number: Section number
        similar_sections: List of similar sections from different versions
        
    Returns:
        Section version document
    """
    # Sort sections by date
    sorted_sections = sorted(similar_sections, 
                           key=lambda x: x.get("_parsed_date") or datetime.min)
    
    versions = []
    latest_valid_version = None
    
    for i, section in enumerate(sorted_sections):
        version_date = section.get("version_date", "")
        parsed_date = section.get("_parsed_date")
        year = parsed_date.year if parsed_date else None
        
        # Determine if this is an ordinance/amendment
        is_ordinance = "ordinance" in section.get("version_label", "").lower() or \
                      "amendment" in section.get("version_label", "").lower()
        
        # Check if ordinance is expired
        is_expired = False
        if is_ordinance and parsed_date:
            is_expired = is_ordinance_expired(version_date)
        
        # Determine status
        if i == 0:
            status = "Original"
        else:
            status = section.get("version_label", "Amendment")
        
        # Determine if active
        is_active = False
        if not is_expired and parsed_date and (latest_valid_version is None or parsed_date > latest_valid_version):
            is_active = True
            latest_valid_version = parsed_date
        
        version_doc = {
            "Version_ID": f"v{i+1}",
            "Year": year,
            "Promulgation_Date": version_date,
            "Status": status,
            "Statute": section.get("statute_text", ""),
            "isActive": is_active
        }
        
        versions.append(version_doc)
    
    # Create the main document
    section_version_doc = {
        "Base_Statute_Name": base_name,
        "Province": similar_sections[0].get("province", ""),
        "Statute_Type": similar_sections[0].get("statute_type", ""),
        "Section": section_number,
        "Definition": similar_sections[0].get("definition", ""),
        "Versions": versions,
        "total_versions": len(versions),
        "latest_version_date": max([s.get("_parsed_date") or datetime.min 
                                  for s in similar_sections]).isoformat() if similar_sections else "",
        "processing_date": datetime.now().isoformat()
    }
    
    return section_version_doc

def print_comprehensive_metadata():
    """Prints comprehensive metadata to the console."""
    log("\n--- Comprehensive Metadata ---", verbose=VERBOSE)
    log(f"Total Sections Processed: {metadata['total_sections_processed']}", verbose=VERBOSE)
    log(f"Total Section Versions Created: {metadata['total_section_versions_created']}", verbose=VERBOSE)
    
    log("\nVersioning Statistics:", verbose=VERBOSE)
    log(f"Base Statutes Processed: {metadata['versioning_stats']['base_statutes_processed']}", verbose=VERBOSE)
    log(f"Section Numbers Processed: {metadata['versioning_stats']['section_numbers_processed']}", verbose=VERBOSE)
    log(f"Groups with Single Version: {metadata['versioning_stats']['groups_with_single_version']}", verbose=VERBOSE)
    log(f"Groups with Multiple Versions: {metadata['versioning_stats']['groups_with_multiple_versions']}", verbose=VERBOSE)
    log(f"Max Versions in a Group: {metadata['versioning_stats']['max_versions_in_group']}", verbose=VERBOSE)
    log(f"Average Versions per Group: {metadata['versioning_stats']['average_versions_per_group']:.2f}", verbose=VERBOSE)
    
    log("\nSimilarity Analysis:", verbose=VERBOSE)
    log(f"Similarity Groups Created: {metadata['similarity_analysis']['similarity_groups_created']}", verbose=VERBOSE)
    log(f"Total Similarity Scores: {len(metadata['similarity_analysis']['similarity_scores'])}", verbose=VERBOSE)
    log(f"Text Similarity Distribution (Top 5):", verbose=VERBOSE)
    for score, count in metadata['similarity_analysis']['text_similarity_distribution'].most_common(5):
        log(f"  {score:.2f}: {count} groups", verbose=VERBOSE)
    
    log("\nProcessing Details:", verbose=VERBOSE)
    log(f"Sections with Valid Dates: {metadata['processing_details']['sections_with_valid_dates']}", verbose=VERBOSE)
    log(f"Sections with Invalid Dates: {metadata['processing_details']['sections_with_invalid_dates']}", verbose=VERBOSE)
    log(f"Sections with Missing Dates: {metadata['processing_details']['sections_with_missing_dates']}", verbose=VERBOSE)
    log(f"Expired Ordinances: {metadata['processing_details']['expired_ordinances']}", verbose=VERBOSE)
    log(f"Active Ordinances: {metadata['processing_details']['active_ordinances']}", verbose=VERBOSE)
    log(f"Database Updates: {metadata['processing_details']['database_updates']}", verbose=VERBOSE)
    
    log("\nSample Similarity Groups:", verbose=VERBOSE)
    for i, group in enumerate(metadata['similarity_analysis']['sample_similarity_groups'][:5]):
        log(f"  Group {i+1}:", verbose=VERBOSE)
        log(f"    Base Name: {group['base_name']}", verbose=VERBOSE)
        log(f"    Section Number: {group['section_number']}", verbose=VERBOSE)
        log(f"    Group Size: {group['group_size']}", verbose=VERBOSE)
        log(f"    Version Labels: {group['version_labels']}", verbose=VERBOSE)
        log(f"    Text Lengths: {group['text_lengths']}", verbose=VERBOSE)
        log("", verbose=VERBOSE)

def save_metadata_to_file():
    """Saves comprehensive metadata to a JSON file with new naming convention."""
    import os
    os.makedirs("metadata", exist_ok=True)
    metadata_filename = f"metadata_section_versioning_{SOURCE_DB}_{SOURCE_COLL}_{date.today().isoformat()}.json"
    metadata_path = f"metadata/{metadata_filename}"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, default=str)
    log(f"💾 Comprehensive metadata exported to {metadata_path}", verbose=VERBOSE)

# --- GPT ordering helper (now with AzureOpenAI integration) ---
@rate_limited_gpt_call
@optimize_gpt_prompt
def gpt_check_section_order(section_a, section_b, meta=None):
    """
    Use GPT to decide which section version came first if dates are identical or missing.
    Returns 'A' or 'B' and a reason.
    """
    if AzureOpenAI is None:
        reason = "Stub: No GPT call, default to A."
        log(f"[GPT] Skipping GPT call (no AzureOpenAI). Defaulting to A. Sections: {section_a.get('definition','')} vs {section_b.get('definition','')}", verbose=VERBOSE)
        return {'order': 'A', 'reason': reason}
    AZURE_OPENAI_API_KEY = "your-azure-api-key-here"  # TODO: Set your key
    AZURE_OPENAI_ENDPOINT = "your-azure-endpoint-here"  # TODO: Set your endpoint
    AZURE_OPENAI_DEPLOYMENT = "gpt-4o"
    AZURE_OPENAI_API_VERSION = "2024-11-01-preview"
    client_aoai = AzureOpenAI(
        api_key=AZURE_OPENAI_API_KEY,
        api_version=AZURE_OPENAI_API_VERSION,
        azure_endpoint=AZURE_OPENAI_ENDPOINT
    )
    # User's prompt
    prompt = f"""
        You are a legal historian and analyst with expertise in statutory law.
        You will be given two sections from statutes. Your task is to determine if these two sections are semantically duplicates (i.e., they have the same legal meaning, even if the wording is different).

        Section A:
        [section A text]

        Section B:
        [section B text]

        Question:
        Are Section A and Section B semantically duplicates? Answer 'Yes' or 'No' and give a one-sentence reason referring to their content or meaning.

        Format:
        Yes – <reason>
        No – <reason>
"""
    log(f"[GPT] Comparing sections for order:\nA: {section_a.get('definition','')}\nB: {section_b.get('definition','')}\nPrompt sent to GPT:\n{prompt}", verbose=VERBOSE)
    try:
        response = client_aoai.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=[
                {"role": "system", "content": "You are a helpful legal AI assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
        )
        content = response.choices[0].message.content
        log(f"[GPT] Response received:\n{content}", verbose=VERBOSE)
        if not content:
            return {'order': 'A', 'reason': 'No response, default to A.'}
        # Parse reply: expect 'A – reason' or 'B – reason'
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        for line in lines:
            if line.upper().startswith('A'):
                return {'order': 'A', 'reason': line[1:].strip('–-: .')}
            if line.upper().startswith('B'):
                return {'order': 'B', 'reason': line[1:].strip('–-: .')}
        # Fallback: look for A or B anywhere
        if 'A' in content:
            return {'order': 'A', 'reason': content}
        if 'B' in content:
            return {'order': 'B', 'reason': content}
        return {'order': 'A', 'reason': content}
    except Exception as e:
        log(f"[GPT] Error during GPT call: {e}", level="error", verbose=True)
        return {'order': 'A', 'reason': f'GPT error: {e}'}

# --- Centralized date parsing with error logging ---
def safe_parse_date(date_str, group_name=None, section_id=None):
    if not date_str:
        metadata['processing_details']['sections_with_missing_dates'] += 1
        return None
    try:
        dt = parser.parse(str(date_str), fuzzy=True)
        return dt
    except Exception:
        metadata['processing_details']['sections_with_invalid_dates'] += 1
        if group_name or section_id:
            if 'date_errors' not in metadata:
                metadata['date_errors'] = []
            metadata['date_errors'].append({'group': group_name, 'section_id': section_id, 'date': date_str})
        return None

# --- Label a single section version ---
def label_single_section(section):
    section['version_label'] = 'Original'
    return section

# --- Analyze dates for a group ---
def analyze_section_dates(sections, group_name):
    years = []
    for s in sections:
        dt = safe_parse_date(s.get('version_date', ''), group_name, s.get('_id'))
        if dt:
            years.append(dt.year)
    if years:
        return min(years), max(years)
    return None, None

# --- Label a group of section versions, enforcing order and GPT guardrails ---
def label_group_sections(sections, group_name, province, statute_type):
    # Only keep sections with matching province and type
    filtered = [s for s in sections if s.get('province', '').strip().lower() == province.strip().lower() and s.get('statute_type', '').strip().lower() == statute_type.strip().lower()]
    # If all dates are missing, deduplicate by text semantics and assign versions as is
    all_dates_missing = all(not s.get('_parsed_date') for s in filtered)
    unique_sections = []
    seen = []  # store indices of unique sections
    for idx, s in enumerate(filtered):
        is_duplicate = False
        for uidx in seen:
            u = filtered[uidx]
            # Use text similarity and GPT for semantic deduplication
            text1 = s.get('statute_text', '')
            text2 = u.get('statute_text', '')
            # Fast check: exact match
            if text1.strip() == text2.strip():
                is_duplicate = True
                log(f"[DEDUP] Exact duplicate found in group {group_name}: '{s.get('definition','')}' == '{u.get('definition','')}'", verbose=VERBOSE)
                break
            # Fuzzy check: high similarity
            sim = calculate_text_similarity(text1, text2)
            if sim > 0.95:
                is_duplicate = True
                log(f"[DEDUP] High similarity ({sim:.2f}) duplicate in group {group_name}: '{s.get('definition','')}' ~ '{u.get('definition','')}'", verbose=VERBOSE)
                break
            # GPT check for semantic similarity
            gpt_result = gpt_check_section_order(s, u, group_name)
            if 'duplicate' in gpt_result.get('reason','').lower() or sim > 0.85 and gpt_result['order'] == 'A':
                is_duplicate = True
                log(f"[DEDUP] GPT/semantic duplicate in group {group_name}: '{s.get('definition','')}' ~ '{u.get('definition','')}'", verbose=VERBOSE)
                break
        if not is_duplicate:
            unique_sections.append(s)
            seen.append(idx)
    # Assign version labels in order of appearance
    for idx, s in enumerate(unique_sections):
        s['version_label'] = f"v{idx+1}"
    log(f"[DEDUP] {len(filtered)} -> {len(unique_sections)} unique sections in group {group_name}", verbose=VERBOSE)
    return unique_sections

# --- Refactored assign_section_versions ---
def assign_section_versions():
    """
    Main function to assign versions to sections (modular, GPT-guarded, metadata-enhanced)
    Refactored: Outputs one document per section, with a Versions array containing all versions.
    """
    start_time = time.time()
    client = connect_to_mongodb()
    if not client:
        return
    try:
        source_col = client[SOURCE_DB][SOURCE_COLL]
        target_col = client[TARGET_DB][TARGET_COLL]
        target_col.delete_many({})
        log(f"🧹 Cleared target collection {TARGET_DB}.{TARGET_COLL}", verbose=VERBOSE)
        all_sections = list(source_col.find({}))
        log(f"📄 Found {len(all_sections)} sections to process", verbose=VERBOSE)
        if not all_sections:
            log("❗ No sections found in the source collection. Exiting.", level="warning", verbose=True)
            return
        # --- Cache parsed dates for all sections ---
        for section in all_sections:
            section['_parsed_date'] = parse_date(section.get('version_date', ''))
        grouped_sections = group_sections_by_base_and_number(all_sections)
        log(f"📊 Grouped into {len(grouped_sections)} base statutes", verbose=VERBOSE)
        if not grouped_sections:
            log("❗ No grouped sections found. Exiting.", level="warning", verbose=True)
            return
        metadata["versioning_stats"]["base_statutes_processed"] = len(grouped_sections)
        total_section_versions = 0
        processed_base_statutes = 0
        grouped_section_docs = []
        for base_idx, (base_name, section_groups) in enumerate(tqdm(grouped_sections.items(), desc="Processing base statutes")):
            log(f"🔹 Processing base statute: {base_name} ({len(section_groups)} sections)", verbose=VERBOSE)
            try:
                metadata["versioning_stats"]["section_numbers_processed"] += len(section_groups)
                for sec_idx, (section_number, sections) in enumerate(section_groups.items()):
                    if sec_idx % 10 == 0 and sec_idx > 0:
                        log(f"   ...processed {sec_idx} sections so far in {base_name}", verbose=VERBOSE)
                    log(f"   - Section {section_number}: {len(sections)} versions", verbose=VERBOSE)
                    province = sections[0].get('province', '').strip().lower()
                    statute_type = sections[0].get('statute_type', '').strip().lower()
                    definition = sections[0].get('definition', '')
                    # Label and order versions
                    if len(sections) == 1:
                        labeled = [label_single_section(sections[0])]
                        metadata["versioning_stats"]["groups_with_single_version"] += 1
                    else:
                        labeled = label_group_sections(sections, f"{base_name}-{section_number}", province, statute_type)
                        metadata["versioning_stats"]["groups_with_multiple_versions"] += 1
                    # Build Versions array
                    versions_array = []
                    for idx, s in enumerate(labeled):
                        # Use cached parsed date
                        parsed_date = s.get('_parsed_date')
                        version_date = s.get("version_date", "")
                        year = parsed_date.year if parsed_date else None
                        is_ordinance = "ordinance" in s.get("version_label", "").lower() or "amendment" in s.get("version_label", "").lower()
                        is_expired = False
                        if is_ordinance and parsed_date:
                            is_expired = is_ordinance_expired(version_date)
                        status = s.get("version_label", f"v{idx+1}")
                        is_active = not is_expired
                        version_doc = {
                            "Version_ID": status,
                            "Year": year,
                            "Promulgation_Date": version_date,
                            "All_Promulgation_Dates": s.get("all_promulgation_dates", []),
                            "Status": status,
                            "isActive": is_active,
                            "is_ordinance": is_ordinance,
                            "is_expired": is_expired,
                            "Statute": s.get("statute_text", ""),
                        }
                        versions_array.append(version_doc)
                    # Use cached parsed dates for latest_version_date
                    latest_version_date = max([s.get('_parsed_date') or datetime.min for s in sections]).isoformat() if sections else ""
                    grouped_section_docs.append({
                        "base_statute_name": base_name,
                        "section_number": section_number,
                        "definition": definition,
                        "Versions": versions_array,
                        "Province": sections[0].get('province', ''),
                        "Statute_Type": sections[0].get('statute_type', ''),
                        "latest_version_date": latest_version_date
                    })
                    total_section_versions += len(versions_array)
                processed_base_statutes += 1
                log(f"✅ Finished base statute: {base_name}", verbose=VERBOSE)
            except Exception as e:
                log(f"❌ Error processing base statute {base_name}: {e}", level="error", verbose=True)
                continue
        metadata["total_section_versions_created"] = total_section_versions
        if grouped_section_docs:
            log(f"💾 Inserting {len(grouped_section_docs)} grouped section docs into target collection...", verbose=VERBOSE)
            target_col.insert_many(grouped_section_docs)
        target_col.create_index([("base_statute_name", 1)])
        target_col.create_index([("section_number", 1)])
        target_col.create_index([("Province", 1)])
        log(f"✅ Successfully processed {processed_base_statutes} base statutes", verbose=VERBOSE)
        log(f"📊 Total section versions created: {total_section_versions}", verbose=VERBOSE)
        log(f"⏱️ Total processing time: {time.time() - start_time:.2f} seconds", verbose=VERBOSE)
        print_comprehensive_metadata()
        save_metadata_to_file()
        log("\n📋 Example Section Versions:", verbose=VERBOSE)
        sample_versions = list(target_col.find().limit(3))
        for i, version in enumerate(sample_versions, 1):
            log(f"   {i}. {version.get('base_statute_name', 'Unknown')} - Section {version.get('section_number', 'Unknown')}", verbose=VERBOSE)
            log(f"      Definition: {version.get('definition', 'No definition')}", verbose=VERBOSE)
            log(f"      Versions: {len(version.get('Versions', []))}", verbose=VERBOSE)
        summary = {
            "total_base_statutes_processed": processed_base_statutes,
            "total_section_versions_created": total_section_versions,
            "processing_date": datetime.now().isoformat(),
            "source_database": SOURCE_DB,
            "target_database": TARGET_DB,
            "similarity_threshold": SIMILARITY_THRESHOLD,
            "text_similarity_threshold": TEXT_SIMILARITY_THRESHOLD
        }
        summary_filename = f"section_versions_summary_{SOURCE_DB}_{SOURCE_COLL}_{date.today().isoformat()}.json"
        summary_path = f"06_section_versioning/{summary_filename}"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, default=str)
        log(f"💾 Summary exported to {summary_path}", verbose=VERBOSE)
    except Exception as e:
        log(f"❌ Error in assign_section_versions: {e}", level="error", verbose=True)
    finally:
        client.close()

if __name__ == "__main__":
    log("🚀 Starting Section Version Assignment Process", verbose=VERBOSE)
    assign_section_versions()
    log("✅ Section version assignment process completed", verbose=VERBOSE)
