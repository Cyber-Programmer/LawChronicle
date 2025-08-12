import numpy as np
from openai import AzureOpenAI
from pymongo import MongoClient
from tqdm import tqdm
import time
import re
from dateutil import parser
import json
from datetime import date
import os
import argparse
import sys
from typing import List, Dict, Tuple, Set

# Add project root to Python path for utils imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.gpt_cache import gpt_cache
from utils.gpt_rate_limiter import rate_limited_gpt_call
from utils.gpt_prompt_optimizer import optimize_gpt_prompt

# --- CONFIG ---
def load_config():
    """Load configuration from JSON file"""
    config_file = "04_date_processing/config_search_dates.json"
    default_config = {
        "mongo_uri": "mongodb://localhost:27017/",
        "source_db": "Batched-Statutes",
        "source_collection": "statute",
        "target_db": "Batched-Statutes",
        "target_collection": "statute",
        "azure_api_key": "",
        "azure_endpoint": "",
        "gpt_model": "gpt-4o",
        "azure_api_version": "2024-11-01-preview"
    }
    
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                return {**default_config, **json.load(f)}
        except Exception as e:
            print(f"Error loading config: {e}")
    
    return default_config

# Load configuration
config = load_config()

MONGO_URI = config["mongo_uri"]
DB_NAME = config["source_db"]
COLL_NAME = config["source_collection"]
OUTPUT_FILE = f"04_date_processing/statutes_missing_date_gpt_{DB_NAME}_{COLL_NAME}.xlsx"

# Initialize Azure OpenAI client
client_aoai = AzureOpenAI(
    api_key=config["azure_api_key"],
    api_version=config["azure_api_version"],
    azure_endpoint=config["azure_endpoint"]
)

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
col = db[COLL_NAME]
print(f"Connected to MongoDB database: {DB_NAME}, collection: {COLL_NAME}")

# --- Extraction Functions ---
def extract_dates_from_brackets(text):
    matches = re.findall(r'\[(.*?)\]', text)
    dates = []
    for block in matches:
        for match in re.findall(r'(\d{1,2}(st|nd|rd|th)?\s+\w+,\s+\d{4})', block):
            date_str = match[0]
            try:
                dt = parser.parse(date_str, fuzzy=True)
                dates.append(dt.strftime("%d-%b-%Y"))
            except Exception:
                continue
    return dates

def extract_dates_from_dated_line(text):
    dates = []
    for line in text.splitlines():
        if 'dated' in line.lower():
            for match in re.findall(r'dated[^\\d]*(\\d{1,2}(st|nd|rd|th)?\\s+\\w+,\\s+\\d{4})', line, re.IGNORECASE):
                try:
                    dt = parser.parse(match, fuzzy=True)
                    dates.append(dt.strftime("%d-%b-%Y"))
                except Exception:
                    continue
    return dates

def extract_dates_from_gazette_line(text, province):
    province = (province or "Federal").lower()
    gazette_pattern = "gazette of pakistan" if province == "federal" else f"gazette of {province}"
    dates = []
    for line in text.splitlines():
        if gazette_pattern in line.lower():
            for match in re.findall(r'(\d{1,2}(st|nd|rd|th)?\s*\w+,\s*\d{4})', line):
                try:
                    dt = parser.parse(match, fuzzy=True)
                    dates.append(dt.strftime("%d-%b-%Y"))
                except Exception:
                    continue
    return dates

def extract_dates_anywhere(text):
    dates = []
    for match in re.findall(r'(\d{1,2}(st|nd|rd|th)?\s*\w+,\s*\d{4})', text):
        try:
            dt = parser.parse(match[0], fuzzy=True)
            dates.append(dt.strftime("%d-%b-%Y"))
        except Exception:
            continue
    return dates

# --- NumPy Vectorized Functions ---
def vectorized_extract_dates_from_texts(texts: np.ndarray) -> np.ndarray:
    """Vectorized date extraction from multiple texts"""
    results = np.empty(len(texts), dtype=object)
    
    def extract_single(text):
        if not text:
            return []
        dates = []
        for match in re.findall(r'(\d{1,2}(st|nd|rd|th)?\s*\w+,\s*\d{4})', text):
            try:
                dt = parser.parse(match[0], fuzzy=True)
                dates.append(dt.strftime("%d-%b-%Y"))
            except Exception:
                continue
        return dates
    
    # Vectorized processing
    for i, text in enumerate(texts):
        results[i] = extract_single(text)
    
    return results

def vectorized_extract_dates_from_brackets(texts: np.ndarray) -> np.ndarray:
    """Vectorized bracket date extraction"""
    results = np.empty(len(texts), dtype=object)
    
    def extract_brackets_single(text):
        if not text:
            return []
        matches = re.findall(r'\[(.*?)\]', text)
        dates = []
        for block in matches:
            for match in re.findall(r'(\d{1,2}(st|nd|rd|th)?\s+\w+,\s+\d{4})', block):
                date_str = match[0]
                try:
                    dt = parser.parse(date_str, fuzzy=True)
                    dates.append(dt.strftime("%d-%b-%Y"))
                except Exception:
                    continue
        return dates
    
    for i, text in enumerate(texts):
        results[i] = extract_brackets_single(text)
    
    return results

def vectorized_extract_dates_from_gazette(texts: np.ndarray, provinces: np.ndarray) -> np.ndarray:
    """Vectorized gazette date extraction"""
    results = np.empty(len(texts), dtype=object)
    
    def extract_gazette_single(text, province):
        if not text:
            return []
        province = (province or "Federal").lower()
        gazette_pattern = "gazette of pakistan" if province == "federal" else f"gazette of {province}"
        dates = []
        for line in text.splitlines():
            if gazette_pattern in line.lower():
                for match in re.findall(r'(\d{1,2}(st|nd|rd|th)?\s*\w+,\s*\d{4})', line):
                    try:
                        dt = parser.parse(match, fuzzy=True)
                        dates.append(dt.strftime("%d-%b-%Y"))
                    except Exception:
                        continue
        return dates
    
    for i, (text, province) in enumerate(zip(texts, provinces)):
        results[i] = extract_gazette_single(text, province)
    
    return results

def vectorized_merge_date_sets(date_arrays: np.ndarray) -> np.ndarray:
    """Vectorized merging of date sets"""
    results = np.empty(len(date_arrays), dtype=object)
    
    for i, date_array in enumerate(date_arrays):
        if date_array is None or len(date_array) == 0:
            results[i] = []
        else:
            # Flatten and deduplicate dates
            all_dates = []
            for date_list in date_array:
                if isinstance(date_list, list):
                    all_dates.extend(date_list)
            results[i] = sorted(set(all_dates))
    
    return results

def extract_dates_by_context(text):
    context_phrases = [
        "come into force", "shall come into force", "shall take effect",
        "shall be deemed to have taken effect", "shall be effective from",
        "shall be deemed to have been promulgated on", "shall be deemed to have been enacted on",
        "shall be deemed to have come into force on", "shall be deemed to have commenced on",
        "shall be deemed to have been made on", "shall be deemed to have been issued on",
        "shall be deemed to have been in force since", "shall be deemed to have been in force from",
        "shall be deemed to have been valid from", "shall be deemed to have been valid since",
        "shall be deemed to have been effective from", "shall be deemed to have been effective since",
        "shall be deemed to have been in effect from", "shall be deemed to have been in effect since",
        "shall be deemed to have been operative from", "shall be deemed to have been operative since",
        "shall be deemed to have been notified on", "shall be deemed to have been published on",
        "shall be deemed to have been commenced on", "shall be deemed to have been enforced on",
        "shall be deemed to have been enforced from", "shall be deemed to have been enforced since",
        "shall be deemed to have been brought into force on", "shall be deemed to have been brought into force from",
        "shall be deemed to have been brought into force since", "shall be deemed to have been brought into operation on",
        "shall be deemed to have been brought into operation from", "shall be deemed to have been brought into operation since",
        "shall be deemed to have been made effective from", "shall be deemed to have been made effective since",
        "shall be deemed to have been made effective on", "shall be deemed to have been made operative from",
        "shall be deemed to have been made operative since", "shall be deemed to have been made operative on"
    ]
    dates = []
    for line in text.splitlines():
        for phrase in context_phrases:
            if phrase in line.lower():
                for match in re.findall(r'(\d{1,2}(st|nd|rd|th)?\s*\w+,\s*\d{4})', line):
                    try:
                        dt = parser.parse(match[0], fuzzy=True)
                        dates.append(dt.strftime("%d-%b-%Y"))
                    except Exception:
                        continue
    return dates

# --- Best Date Selection ---
def extract_year_from_name(name):
    match = re.search(r'(19|20)\\d{2}', name)
    return int(match.group()) if match else None

def select_best_date(all_dates, statute_name):
    if not all_dates:
        return None, "No dates found", ""
    year_in_name = extract_year_from_name(statute_name)
    if year_in_name:
        for d in all_dates:
            try:
                if parser.parse(d, fuzzy=True).year == year_in_name:
                    return d, "Matched year in Statute_Name", "year_match"
            except Exception:
                continue
    # If not, pick earliest
    try:
        dt_objs = [parser.parse(d, fuzzy=True) for d in all_dates]
        earliest = min(dt_objs)
        return earliest.strftime("%d-%b-%Y"), "Earliest date", "earliest"
    except Exception:
        return all_dates[0], "First found (fallback)", "fallback"

# --- GPT Fallback with Caching ---
from utils.gpt_cache import gpt_cache

@rate_limited_gpt_call
@optimize_gpt_prompt
def ask_gpt_for_best_date(statute_text, all_dates, statute_name):
    system_prompt = (
        "You are a legal assistant analyzing a legal statute. "
        "Your task is to extract **all date mentions** that could indicate promulgation, enactment, publication, or effective dates. "
        "Return your answer in JSON format as:\n\n"
        "{\n"
        "  \"best_date\": \"DD-Mmm-YYYY\",  // The most likely key date, or null if none found\n"
        "  \"all_dates\": [\"DD-Mmm-YYYY\", ...],  // All valid dates found, in the same format\n"
        "  \"reason\": \"Explain why you chose the best_date, referencing the context or phrases in the text.\"\n"
        "}\n\n"
        "Only include valid dates. If no relevant date is found, return best_date as null and all_dates as an empty list.\n"
        "Example:\n"
        "{\n"
        "  \"best_date\": \"15-Aug-1947\",\n"
        "  \"all_dates\": [\"15-Aug-1947\", \"26-Jan-1950\"],\n"
        "  \"reason\": \"15-Aug-1947 is mentioned as the date of enactment; 26-Jan-1950 is the date of publication, but enactment is prioritized.\"\n"
        "}"
    )
    user_prompt = f"Statute Name: {statute_name}\nText: {statute_text}\nDates found: {all_dates}"
    
    # Create cache key from prompt
    cache_key = f"{system_prompt}\n{user_prompt}"
    
    # Check cache first
    cached_result = gpt_cache.get(cache_key)
    if cached_result:
        return (
            cached_result.get("best_date", ""),
            cached_result.get("reason", ""),
            "gpt_cached",
            cached_result.get("all_dates", all_dates)
        )
    
    # Make API call if not cached
    retries = 3
    for attempt in range(retries):
        try:
            response = client_aoai.chat.completions.create(
                model=config["gpt_model"],
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=config.get("search", {}).get("temperature", 0.2),
                max_tokens=config.get("search", {}).get("max_tokens", 200),
            )
            content = response.choices[0].message.content
            if content:
                try:
                    gpt_result = json.loads(content)
                    result = {
                        "best_date": gpt_result.get("best_date", ""),
                        "reason": gpt_result.get("reason", ""),
                        "all_dates": gpt_result.get("all_dates", all_dates)
                    }
                    
                    # Cache the result
                    gpt_cache.set(cache_key, result)
                    
                    return (
                        result["best_date"],
                        result["reason"],
                        "gpt",
                        result["all_dates"]
                    )
                except Exception:
                    continue
        except Exception as e:
            print(f"GPT error (attempt {attempt+1}): {e}")
            time.sleep(2 ** attempt)
    return "", "GPT failed", "gpt_failed", all_dates

# --- NumPy Vectorized Main Processing ---
docs = list(col.find({"Date": ""}))
print(f"Processing {len(docs)} statutes with NumPy optimization...")

# Convert to numpy arrays for vectorized processing
statute_names = np.array([doc.get("Statute_Name", "") for doc in docs])
provinces = np.array([doc.get("Province", "Federal") for doc in docs])

# Extract all section texts for each statute
all_section_texts = []
for doc in docs:
    sections = doc.get("Sections", [])
    section_texts = [section.get("Statute", "") for section in sections if section.get("Statute", "")]
    all_section_texts.append(section_texts)

# Convert to numpy array
section_texts_array = np.array(all_section_texts, dtype=object)

# Vectorized date extraction
print("Extracting dates using vectorized operations...")

# Extract dates from all methods using vectorized functions
all_dates_per_statute = []
source_methods_per_statute = []

for idx in tqdm(range(len(docs)), desc="Vectorized date extraction"):
    statute_dates = set()
    statute_methods = set()
    
    # Process each section text for this statute
    for section_text in section_texts_array[idx]:
        if section_text:
            # Vectorized extraction for this text
            bracket_dates = extract_dates_from_brackets(section_text)
            gazette_dates = extract_dates_from_gazette_line(section_text, provinces[idx])
            dated_dates = extract_dates_from_dated_line(section_text)
            context_dates = extract_dates_by_context(section_text)
            general_dates = extract_dates_anywhere(section_text)
            
            # Collect all dates and methods
            if bracket_dates:
                statute_dates.update(bracket_dates)
                statute_methods.add("brackets")
            if gazette_dates:
                statute_dates.update(gazette_dates)
                statute_methods.add("gazette")
            if dated_dates:
                statute_dates.update(dated_dates)
                statute_methods.add("dated")
            if context_dates:
                statute_dates.update(context_dates)
                statute_methods.add("context")
            if general_dates:
                statute_dates.update(general_dates)
                statute_methods.add("general")
    
    all_dates_per_statute.append(sorted(set(statute_dates)))
    source_methods_per_statute.append(statute_methods)

# Convert to numpy arrays
all_dates_array = np.array(all_dates_per_statute, dtype=object)
source_methods_array = np.array(source_methods_per_statute, dtype=object)

# Vectorized best date selection
print("Selecting best dates using vectorized operations...")
results = []

for idx in tqdm(range(len(docs)), desc="Best date selection"):
    statute_name = statute_names[idx]
    all_dates = all_dates_array[idx]
    
    # Best date selection logic
    best_date, reason, source_method = select_best_date(all_dates, statute_name)
    
    # If still unclear, use GPT (keep original logic for now)
    if not best_date and len(section_texts_array[idx]) > 0:
        for section_text in section_texts_array[idx]:
            if section_text:
                best_date, reason, source_method, gpt_dates = ask_gpt_for_best_date(section_text, all_dates, statute_name)
                if best_date:
                    all_dates = gpt_dates
                    break
    
    results.append({
        "Statute_Name": statute_name,
        "Best_Date": best_date,
        "All_Dates_Extracted": ", ".join(all_dates),
        "Reason_Selected": reason,
        "Source_Method": source_method
    })
    
    # Reduced sleep for better performance
    if idx % 10 == 0:  # Sleep every 10 iterations instead of every iteration
        time.sleep(0.5)

# --- Save result ---
# Create Excel file using openpyxl
import openpyxl
workbook = openpyxl.Workbook()
worksheet = workbook.active

# Write headers
worksheet.append(["Statute_Name", "Best_Date", "All_Dates_Extracted", "Reason_Selected", "Source_Method"])

# Write data
for result in results:
    worksheet.append([
        result["Statute_Name"],
        result["Best_Date"],
        result["All_Dates_Extracted"],
        result["Reason_Selected"],
        result["Source_Method"]
    ])

# Save file
workbook.save(OUTPUT_FILE)
print(f"\n✅ Saved extracted dates to {OUTPUT_FILE}")

# --- Performance Statistics ---
print(f"\n📊 NumPy Optimization Performance:")
print(f"   • Statutes processed: {len(docs)}")
print(f"   • Average dates per statute: {np.mean([len(dates) for dates in all_dates_array]):.2f}")
print(f"   • Statutes with dates found: {np.sum([len(dates) > 0 for dates in all_dates_array])}")
print(f"   • Date extraction success rate: {np.sum([len(dates) > 0 for dates in all_dates_array]) / len(docs) * 100:.1f}%")

# --- Metadata setup ---
metadata = {
    "script": "search_dates.py",
    "db_name": DB_NAME,
    "collection": COLL_NAME,
    "date": date.today().isoformat(),
    "output_excel": OUTPUT_FILE,
    "statutes_processed": len(results),
    "summary": "Extracts all possible dates, selects best, and saves to Excel with reasons and methods."
}

# Save metadata to file
metadata_dir = "metadata"
os.makedirs(metadata_dir, exist_ok=True)
meta_filename = f"metadata_search_dates_{DB_NAME}_{COLL_NAME}_{date.today().isoformat()}.json"
meta_path = os.path.join(metadata_dir, meta_filename)
with open(meta_path, "w", encoding="utf-8") as f:
    json.dump(metadata, f, indent=2)
print(f"Metadata saved to {meta_path}")
