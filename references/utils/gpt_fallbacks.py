"""
Smart Fallback System for GPT Calls

This module provides intelligent fallback mechanisms to reduce GPT API calls
by using heuristics and rules before resorting to GPT.
"""

import re
from datetime import datetime
from dateutil import parser
from typing import Dict, Any, Optional, Tuple

def smart_date_selection(all_dates: list, statute_name: str) -> Tuple[str, str, str]:
    """
    Smart date selection using heuristics before GPT.
    
    Returns: (best_date, reason, method)
    """
    if not all_dates:
        return "", "No dates found", "no_dates"
    
    # Heuristic 1: Check if statute name contains a year
    year_match = re.search(r'(19|20)\d{2}', statute_name)
    if year_match:
        target_year = int(year_match.group())
        for date_str in all_dates:
            try:
                parsed_date = parser.parse(date_str, fuzzy=True)
                if parsed_date.year == target_year:
                    return date_str, f"Matched year {target_year} in statute name", "year_match"
            except:
                continue
    
    # Heuristic 2: Look for enactment/promulgation keywords
    enactment_keywords = ['enact', 'promulgate', 'assent', 'commence']
    for date_str in all_dates:
        # This would need context from the original text
        # For now, just check if it's the earliest date
        pass
    
    # Heuristic 3: Select earliest date (most common pattern)
    try:
        parsed_dates = [parser.parse(d, fuzzy=True) for d in all_dates]
        earliest_date = min(parsed_dates)
        earliest_str = earliest_date.strftime("%d-%b-%Y")
        return earliest_str, "Earliest date selected", "earliest_date"
    except:
        pass
    
    # Heuristic 4: Select first date if only one
    if len(all_dates) == 1:
        return all_dates[0], "Only one date found", "single_date"
    
    # Fallback: return first date
    return all_dates[0], "First date (fallback)", "fallback"

def smart_statute_ordering(statute_a: Dict, statute_b: Dict) -> Tuple[str, str]:
    """
    Smart statute ordering using heuristics before GPT.
    
    Returns: ('A' or 'B', reason)
    """
    # Heuristic 1: Date comparison
    date_a = statute_a.get('Date', '')
    date_b = statute_b.get('Date', '')
    
    if date_a and date_b:
        try:
            parsed_a = parser.parse(date_a, fuzzy=True)
            parsed_b = parser.parse(date_b, fuzzy=True)
            if parsed_a != parsed_b:
                return ('A' if parsed_a < parsed_b else 'B', f"Date comparison: {date_a} vs {date_b}")
        except:
            pass
    
    # Heuristic 2: Statute name patterns
    name_a = statute_a.get('Statute_Name', '').lower()
    name_b = statute_b.get('Statute_Name', '').lower()
    
    # Amendments typically come later
    if 'amendment' in name_a and 'amendment' not in name_b:
        return ('B', "Amendment in statute A")
    if 'amendment' in name_b and 'amendment' not in name_a:
        return ('A', "Amendment in statute B")
    
    # Original acts typically come first
    if 'original' in name_a and 'original' not in name_b:
        return ('A', "Original in statute A")
    if 'original' in name_b and 'original' not in name_a:
        return ('B', "Original in statute B")
    
    # Heuristic 3: Version labels
    version_a = statute_a.get('Version_Label', '').lower()
    version_b = statute_b.get('Version_Label', '').lower()
    
    if 'original' in version_a and 'original' not in version_b:
        return ('A', "Original version label")
    if 'original' in version_b and 'original' not in version_a:
        return ('B', "Original version label")
    
    # Heuristic 4: Statute type patterns
    type_a = statute_a.get('Statute_Type', '').lower()
    type_b = statute_b.get('Statute_Type', '').lower()
    
    # Acts typically come before rules/regulations
    type_order = ['act', 'ordinance', 'law', 'rule', 'regulation']
    if type_a in type_order and type_b in type_order:
        idx_a = type_order.index(type_a)
        idx_b = type_order.index(type_b)
        if idx_a != idx_b:
            return ('A' if idx_a < idx_b else 'B', f"Type order: {type_a} vs {type_b}")
    
    # Default: use statute A
    return ('A', "Default fallback")

def smart_section_similarity(section_a: Dict, section_b: Dict) -> Tuple[bool, str]:
    """
    Smart section similarity check using heuristics before GPT.
    
    Returns: (is_similar, reason)
    """
    # Heuristic 1: Section number comparison
    num_a = section_a.get('section_number', '')
    num_b = section_b.get('section_number', '')
    
    if num_a and num_b and num_a == num_b:
        return True, "Same section number"
    
    # Heuristic 2: Definition similarity (simple text comparison)
    def_a = section_a.get('definition', '').lower()
    def_b = section_b.get('definition', '').lower()
    
    if def_a and def_b:
        # Simple word overlap
        words_a = set(def_a.split())
        words_b = set(def_b.split())
        
        if len(words_a) > 0 and len(words_b) > 0:
            overlap = len(words_a.intersection(words_b))
            total_words = len(words_a.union(words_b))
            similarity = overlap / total_words
            
            if similarity > 0.8:
                return True, f"High text similarity: {similarity:.2f}"
            elif similarity > 0.6:
                return True, f"Medium text similarity: {similarity:.2f}"
    
    # Heuristic 3: Statute text similarity
    text_a = section_a.get('statute_text', '').lower()
    text_b = section_b.get('statute_text', '').lower()
    
    if text_a and text_b:
        # Check for exact matches in key phrases
        key_phrases = ['shall', 'may', 'must', 'provided that', 'notwithstanding']
        matches_a = sum(1 for phrase in key_phrases if phrase in text_a)
        matches_b = sum(1 for phrase in key_phrases if phrase in text_b)
        
        if matches_a > 0 and matches_b > 0 and abs(matches_a - matches_b) <= 1:
            return True, f"Similar legal structure: {matches_a} vs {matches_b} key phrases"
    
    # Heuristic 4: Date-based similarity
    date_a = section_a.get('Date', '')
    date_b = section_b.get('Date', '')
    
    if date_a and date_b and date_a == date_b:
        return True, "Same date"
    
    return False, "No similarity detected"

def should_use_gpt_fallback(heuristic_result: Tuple, confidence_threshold: float = 0.7) -> bool:
    """
    Determine if we should use GPT based on heuristic confidence.
    
    Args:
        heuristic_result: Result from heuristic function
        confidence_threshold: Minimum confidence to avoid GPT
    
    Returns:
        True if GPT should be used, False otherwise
    """
    # This is a simplified version - in practice you'd have confidence scores
    # For now, we'll use some simple rules
    
    if 'fallback' in heuristic_result[1].lower():
        return True  # Use GPT for fallback cases
    
    if 'high' in heuristic_result[1].lower():
        return False  # Don't use GPT for high confidence
    
    if 'medium' in heuristic_result[1].lower():
        return True  # Use GPT for medium confidence
    
    return True  # Default to using GPT

# Usage examples
def optimized_date_extraction(statute_text: str, all_dates: list, statute_name: str):
    """Optimized date extraction with smart fallbacks."""
    # Try heuristic first
    best_date, reason, method = smart_date_selection(all_dates, statute_name)
    
    # Only use GPT if heuristic confidence is low
    if should_use_gpt_fallback((best_date, reason, method)):
        # Import and use your existing GPT function
        from your_gpt_module import ask_gpt_for_best_date
        return ask_gpt_for_best_date(statute_text, all_dates, statute_name)
    else:
        return best_date, reason, method

def optimized_statute_ordering(statute_a: Dict, statute_b: Dict):
    """Optimized statute ordering with smart fallbacks."""
    # Try heuristic first
    order, reason = smart_statute_ordering(statute_a, statute_b)
    
    # Only use GPT if heuristic confidence is low
    if should_use_gpt_fallback((order, reason)):
        # Import and use your existing GPT function
        from your_gpt_module import gpt_check_version_order
        return gpt_check_version_order(statute_a, statute_b)
    else:
        return {'order': order, 'reason': reason} 