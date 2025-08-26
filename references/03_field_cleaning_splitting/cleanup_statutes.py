import re
import json
from datetime import date
from pymongo import MongoClient
from openai import AzureOpenAI
from tqdm import tqdm
from dateutil import parser
import numpy as np

# --- CONFIG ---
MONGO_URI = "mongodb://localhost:27017"
SOURCE_DB = "Batched-Statutes-Filled"  # Change as needed
SOURCE_COLL = "batch2"
CLEANED_DB = "Filled-Batch-Cleaned"
CLEANED_COLL = "batch2"
AZURE_OPENAI_API_KEY = "your-azure-api-key-here"
AZURE_OPENAI_ENDPOINT = "your-azure-endpoint-here"
AZURE_OPENAI_DEPLOYMENT = "gpt-4o"
AZURE_OPENAI_API_VERSION = "2024-11-01-preview"

# --- Azure GPT client setup ---
client_aoai = AzureOpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    api_version=AZURE_OPENAI_API_VERSION,
    azure_endpoint=AZURE_OPENAI_ENDPOINT
)

# --- MongoDB setup ---
client = MongoClient(MONGO_URI)
col = client[SOURCE_DB][SOURCE_COLL]
cleaned_col = client[CLEANED_DB][CLEANED_COLL]

# --- Metadata log ---
metadata_log = []

# List of known Pakistani provinces - converted to numpy arrays for faster lookups
PAKISTANI_PROVINCES = np.array([
    'Azad Kashmir And Jammu', 'Balochistan', 'Federal', 'Khyber Pakhtunkhwa', 'Punjab', 'Sindh'
])

FOREIGN_COUNTRY_INDICATORS = np.array([
    'india', 'indian', 'turkey', 'turkish', 'uk', 'united kingdom', 'england', 'scotland', 'wales', 'ireland',
    'united states', 'usa', 'america', 'bangladesh', 'sri lanka', 'nepal', 'afghanistan', 'iran', 'china', 'russia',
    'malaysia', 'canada', 'australia', 'france', 'germany', 'japan', 'italy', 'spain', 'sweden', 'norway', 'denmark',
    'netherlands', 'switzerland', 'belgium', 'brazil', 'mexico', 'south africa', 'egypt', 'indonesia', 'thailand'
])

def is_probably_pakistan_law(doc):
    preamble = doc.get("Preamble", "")
    pattern = re.compile(r"islamic republic( of)? pakistan", re.IGNORECASE)
    return bool(pattern.search(preamble))

def ask_gpt_is_pakistan(preamble, statute_date=None, statute_name=None):
    """
    Calls GPT to check if the preamble describes a law of Pakistan.
    Returns (yes_no, reason)
    """
    system_prompt = (
        """You are a legal expert on the Pakistani legal system.  
You will be given the preamble of a statute.  

Question:  
“Does this preamble describe or relate to a law of Pakistan (federal or provincial)? Or is it from another country or any of its provinces or cities or an international instrument that makes no reference to Pakistan?”  

Instructions:  
- Answer **Yes** or **No**.  
- Provide a one‑sentence reason.  
- If a statute name or date is available, you may consider it to inform your decision.

Format:  
Yes – <one‑sentence reason>  
No  – <one‑sentence reason>
"""
    )
    user_prompt = f"Preamble: {preamble}\n"
    if statute_date:
        user_prompt += f"Date: {statute_date}\n"
    if statute_name:
        user_prompt += f"Statute Name: {statute_name}\n"
    try:
        response = client_aoai.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2,
        )
        content = response.choices[0].message.content.strip()
        if content.lower().startswith("yes"):
            return ("Yes", content)
        elif content.lower().startswith("no"):
            return ("No", content)
        else:
            return ("Unknown", content)
    except Exception as e:
        return ("Error", f"GPT error: {e}")

def extract_name_from_preamble(doc):
    preamble = doc.get("Preamble", "")
    match = re.search(r"An Act to[^'\"]*['\"]([^'\"]+)['\"]", preamble, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    match = re.search(r"['\"]([^'\"]+)['\"]", preamble)
    if match:
        return match.group(1).strip()
    first_line = preamble.splitlines()[0] if preamble else ""
    return first_line.strip() if first_line else None

def log_action(doc_id, original_name, action, reason, gpt_reason=None, province=None, preamble=None):
    entry = {
        "_id": str(doc_id),
        "original_name": original_name,
        "action": action,
        "reason": reason,
        "province": province,
        "preamble": preamble
    }
    if gpt_reason is not None:
        entry["gpt_reason"] = gpt_reason
    metadata_log.append(entry)

def is_pakistani_statute_name(name):
    pattern = re.compile(r"(Act|Ordinance|Order|Regulation|Rule|Constitution|Amendment|Bill|Code|Statute|Law)$", re.IGNORECASE)
    return bool(pattern.search(name or ""))

def is_pre_1947_law(doc):
    date_str = doc.get('Date', '')
    try:
        if not date_str:
            return False  # If no date, don't drop solely for this
        dt = parser.parse(date_str, fuzzy=True, dayfirst=True)
        return dt.year < 1947
    except Exception:
        return False

def mentions_gazette_of_pakistan(preamble):
    return bool(re.search(r"gazette of pakistan", preamble, re.IGNORECASE))

def mentions_gazette_of_province(preamble, province):
    if not province or province.lower() == 'federal':
        return False
    # e.g., Gazette of Punjab, Gazette of Sindh, etc.
    pattern = rf"gazette of {re.escape(province.lower())}"
    return bool(re.search(pattern, preamble.lower()))

def contains_pakistan_or_province(*fields):
    """
    Check if any of the provided fields contain Pakistan or a Pakistani province.
    Uses numpy for faster string matching.
    """
    keywords = np.array(["pakistan"] + [p.lower() for p in PAKISTANI_PROVINCES])
    
    for field in fields:
        if not field:
            continue
        field_lower = field.lower()
        # Use numpy for faster keyword matching
        if np.any(np.char.find(keywords, field_lower) >= 0):
            return True
    return False

def is_foreign_constitution_or_law(statute_name, preamble):
    """
    Check if the statute is a foreign constitution or law.
    Uses numpy for faster country indicator matching.
    """
    text = (statute_name or '') + ' ' + (preamble or '')
    text_lower = text.lower()
    
    # Use numpy for faster country indicator matching
    country_matches = np.char.find(FOREIGN_COUNTRY_INDICATORS, text_lower) >= 0
    if np.any(country_matches):
        # If 'pakistan' is also present, it's not foreign
        if 'pakistan' not in text_lower:
            return True
    return False

def main():
    total_scanned = 0
    total_dropped = 0
    total_renamed = 0
    total_kept = 0
    today_str = date.today().strftime("%d-%m-%Y")
    metadata_filename = f"cleanup_{CLEANED_DB}_{CLEANED_COLL}_{today_str}.json"
    cleaned_col.drop()  # Start fresh each run
    all_docs = list(col.find({}))
    for doc in tqdm(all_docs, desc="Processing statutes"):
        total_scanned += 1
        doc_id = doc.get("_id")
        original_name = doc.get("Statute_Name", "")
        preamble = doc.get("Preamble", "")
        statute_date = doc.get("Date", "")
        province = doc.get("Province", "")
        doc_copy = dict(doc)  # Work on a copy for insertion
        # 0. Drop pre-1947 laws
        if is_pre_1947_law(doc):
            total_dropped += 1
            log_action(doc_id, original_name, "dropped", "pre-1947 law", None, province, preamble)
            continue
        # 0.5 Drop foreign constitutions/laws
        if is_foreign_constitution_or_law(original_name, preamble):
            total_dropped += 1
            log_action(doc_id, original_name, "dropped", "foreign constitution/law detected", None, province, preamble)
            continue
        # 1. Pakistan check (regex + Gazette + GPT + any field contains Pakistan/province)
        gpt_decision = None
        gpt_reason = None
        keep = False
        if is_probably_pakistan_law(doc) or mentions_gazette_of_pakistan(preamble) or mentions_gazette_of_province(preamble, province):
            keep = True
        else:
            gpt_decision, gpt_reason = ask_gpt_is_pakistan(preamble, statute_date, original_name)
            # If any field contains 'Pakistan' or a province, keep
            if contains_pakistan_or_province(original_name, preamble, gpt_reason):
                keep = True
            # If province is a known Pakistani province and date >= 1947, only drop if GPT is very certain it's foreign
            elif province in PAKISTANI_PROVINCES:
                foreign_indicators = ['india', 'indian', 'uk', 'british', 'turkey', 'malaysia', 'canada', 'denmark', 'iran', 'japan', 'kuwait', 'china', 'saudi', 'russia', 'united nations', 'international', 'not pakistan', 'not a law of pakistan']
                if gpt_decision == "No" and any(word in (gpt_reason or '').lower() for word in foreign_indicators):
                    keep = False
                else:
                    keep = True
            else:
                keep = (gpt_decision == "Yes")
        if not keep:
            total_dropped += 1
            log_action(doc_id, original_name, "dropped", "no Pakistan mention + GPT said No", gpt_reason, province, preamble)
            continue
        # 2. For kept statutes, if name is non-Pakistani, try to rename
        if not is_pakistani_statute_name(original_name):
            new_name = extract_name_from_preamble(doc)
            if new_name and new_name != original_name:
                doc_copy["Statute_Name"] = new_name
                total_renamed += 1
                log_action(doc_id, original_name, f"renamed to {new_name}", "name replaced from preamble", None, province, preamble)
        cleaned_col.insert_one(doc_copy)
        total_kept += 1
    # Write metadata
    with open(metadata_filename, "w", encoding="utf-8") as f:
        json.dump(metadata_log, f, indent=2, ensure_ascii=False)
    # Print summary
    print(f"Total scanned: {total_scanned}")
    print(f"Total kept: {total_kept}")
    print(f"Total dropped: {total_dropped}")
    print(f"Total renamed: {total_renamed}")
    print(f"Metadata file: {metadata_filename}")
    print(f"Cleaned collection: {CLEANED_COLL} in DB: {SOURCE_DB}")

if __name__ == "__main__":
    main() 