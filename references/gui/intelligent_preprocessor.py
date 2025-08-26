#!/usr/bin/env python3
"""
Intelligent Preprocessor for Statute Analysis

This module implements rule-based pre-filtering and preprocessing to reduce
false positives and improve performance before making GPT calls.

Features:
- Rule-based pre-filtering
- Year and title disambiguation
- Section renumbering detection
- Language detection and translation
- Performance optimizations
- Output validation
"""

import re
import json
import logging
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass
from datetime import datetime
import numpy as np
from collections import defaultdict
import hashlib

# Language detection
try:
    from langdetect import detect, LangDetectException
    LANGDETECT_AVAILABLE = True
except ImportError:
    LANGDETECT_AVAILABLE = False
    print("⚠️ langdetect not available, using fallback language detection")

# FastText for language detection (alternative)
try:
    import fasttext
    FASTTEXT_AVAILABLE = True
    # Load language detection model
    fasttext_model = fasttext.load_model('lid.176.bin')
except ImportError:
    FASTTEXT_AVAILABLE = False
    print("⚠️ fasttext not available, using fallback language detection")

# Fuzzy string matching
try:
    from rapidfuzz import fuzz, process
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False
    print("⚠️ rapidfuzz not available, using difflib fallback")

@dataclass
class PreprocessingResult:
    """Result of preprocessing analysis"""
    should_use_gpt: bool
    confidence_score: float
    rule_based_classification: Dict
    preprocessing_notes: List[str]
    language_detected: str
    translation_required: bool
    section_similarity: Dict
    year_discrepancy: bool
    title_similarity: float

class IntelligentPreprocessor:
    """Intelligent preprocessing for statute analysis"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.cache = {}
        self.rule_cache = {}
        
        # Load configuration
        self.confidence_threshold = config.get("context_analysis", {}).get("confidence_threshold", 0.7)
        self.max_context_length = config.get("context_analysis", {}).get("max_context_length", 2000)
        self.enable_smart_filtering = config.get("performance", {}).get("enable_smart_filtering", True)
        
        # Initialize language detection
        self._init_language_detection()
        
    def _init_language_detection(self):
        """Initialize language detection capabilities"""
        if LANGDETECT_AVAILABLE:
            self.language_detector = "langdetect"
        elif FASTTEXT_AVAILABLE:
            self.language_detector = "fasttext"
        else:
            self.language_detector = "fallback"
            self.logger.warning("Using fallback language detection")
    
    def preprocess_statute(self, statute: Dict) -> PreprocessingResult:
        """
        Main preprocessing method for a single statute
        
        Returns:
            PreprocessingResult with analysis and recommendations
        """
        preprocessing_notes = []
        
        # 1. Extract basic information
        title = statute.get('Statute_Name', '')
        year = self._extract_year(title)
        text_content = self._extract_text_content(statute)
        
        # 2. Language detection
        language = self._detect_language(text_content)
        translation_required = language != 'en'
        
        # 3. Rule-based classification
        rule_classification = self._apply_rule_based_classification(title, year, text_content)
        
        # 4. Determine if GPT is needed
        should_use_gpt = self._should_use_gpt(rule_classification, title, year)
        
        # 5. Calculate confidence score
        confidence_score = self._calculate_confidence_score(rule_classification, title, year)
        
        # 6. Section analysis (if applicable)
        section_similarity = self._analyze_sections(statute)
        
        # 7. Year discrepancy check
        year_discrepancy = self._check_year_discrepancy(title, year)
        
        # 8. Title similarity analysis
        title_similarity = self._analyze_title_similarity(title)
        
        preprocessing_notes.extend([
            f"Language detected: {language}",
            f"Year extracted: {year}",
            f"Rule classification: {rule_classification['type']}",
            f"Confidence: {confidence_score:.2f}"
        ])
        
        return PreprocessingResult(
            should_use_gpt=should_use_gpt,
            confidence_score=confidence_score,
            rule_based_classification=rule_classification,
            preprocessing_notes=preprocessing_notes,
            language_detected=language,
            translation_required=translation_required,
            section_similarity=section_similarity,
            year_discrepancy=year_discrepancy,
            title_similarity=title_similarity
        )
    
    def preprocess_statute_pair(self, statute_a: Dict, statute_b: Dict) -> Tuple[PreprocessingResult, PreprocessingResult]:
        """
        Preprocess a pair of statutes for relationship analysis
        
        Returns:
            Tuple of PreprocessingResult for both statutes
        """
        result_a = self.preprocess_statute(statute_a)
        result_b = self.preprocess_statute(statute_b)
        
        # Additional pair-specific analysis
        self._analyze_pair_relationship(result_a, result_b, statute_a, statute_b)
        
        return result_a, result_b
    
    def _extract_year(self, title: str) -> Optional[int]:
        """Extract year from statute title"""
        # Common year patterns in legal documents
        year_patterns = [
            r'\b(19|20)\d{2}\b',  # 1900-2099
            r'\b\d{4}\b',         # Any 4-digit number
            r'\b(19|20)\d{2}[-_]\d{2}\b',  # 1999-01 format
        ]
        
        for pattern in year_patterns:
            matches = re.findall(pattern, title)
            if matches:
                try:
                    # Extract the first 4-digit year
                    for match in matches:
                        if isinstance(match, tuple):
                            match = ''.join(match)
                        if len(match) >= 4:
                            year = int(match[:4])
                            if 1900 <= year <= 2099:
                                return year
                except (ValueError, TypeError):
                    continue
        
        return None
    
    def _extract_text_content(self, statute: Dict) -> str:
        """Extract text content from statute for analysis"""
        content_parts = []
        
        # Add preamble if available
        if statute.get('Preamble'):
            content_parts.append(str(statute['Preamble']))
        
        # Add sections if available
        if statute.get('Sections'):
            if isinstance(statute['Sections'], list):
                for section in statute['Sections']:
                    if isinstance(section, dict):
                        content_parts.append(str(section.get('text', '')))
                    else:
                        content_parts.append(str(section))
            else:
                content_parts.append(str(statute['Sections']))
        
        # Add other text fields
        text_fields = ['Long_Title', 'Short_Title', 'Description', 'Notes']
        for field in text_fields:
            if statute.get(field):
                content_parts.append(str(statute[field]))
        
        return ' '.join(content_parts)
    
    def _detect_language(self, text: str) -> str:
        """Detect language of text content"""
        if not text or len(text.strip()) < 10:
            return 'en'  # Default to English for short text
        
        # Clean text for language detection
        clean_text = re.sub(r'[^\w\s]', ' ', text[:1000])  # Use first 1000 chars
        
        try:
            if self.language_detector == "langdetect" and LANGDETECT_AVAILABLE:
                return detect(clean_text)
            elif self.language_detector == "fasttext" and FASTTEXT_AVAILABLE:
                predictions = fasttext_model.predict(clean_text, k=1)
                return predictions[0][0].replace('__label__', '')
            else:
                # Fallback language detection based on character patterns
                return self._fallback_language_detection(clean_text)
        except Exception as e:
            self.logger.warning(f"Language detection failed: {e}")
            return 'en'  # Default to English
    
    def _fallback_language_detection(self, text: str) -> str:
        """Fallback language detection using character patterns"""
        # Urdu/Hindi detection (common in Pakistani legal documents)
        urdu_patterns = [
            r'[\u0600-\u06FF]',  # Arabic script
            r'[\u0750-\u077F]',  # Arabic Supplement
            r'[\u08A0-\u08FF]',  # Arabic Extended-A
        ]
        
        for pattern in urdu_patterns:
            if re.search(pattern, text):
                return 'ur'  # Urdu
        
        # Check for common Urdu words
        urdu_words = ['قانون', 'آئین', 'ترمیم', 'دفعہ', 'آرٹیکل']
        text_lower = text.lower()
        urdu_count = sum(1 for word in urdu_words if word in text_lower)
        
        if urdu_count > 0:
            return 'ur'  # Urdu
        
        return 'en'  # Default to English
    
    def _apply_rule_based_classification(self, title: str, year: Optional[int], text_content: str) -> Dict:
        """Apply rule-based classification without GPT"""
        classification = {
            'type': 'unknown',
            'confidence': 0.0,
            'reasoning': [],
            'amendment_targets': [],
            'constitutional_related': False
        }
        
        title_lower = title.lower()
        text_lower = text_content.lower()
        
        # Rule 1: Constitutional amendment detection
        if 'constitution' in title_lower and 'amendment' in title_lower:
            classification['type'] = 'constitutional_amendment'
            classification['confidence'] = 0.95
            classification['constitutional_related'] = True
            classification['reasoning'].append('Title contains both "constitution" and "amendment"')
        
        # Rule 2: Constitutional order detection
        elif 'constitution' in title_lower and 'order' in title_lower:
            classification['type'] = 'constitutional_order'
            classification['confidence'] = 0.90
            classification['constitutional_related'] = True
            classification['reasoning'].append('Title contains "constitution" and "order"')
        
        # Rule 3: Amendment to ordinary act
        elif 'amendment' in title_lower and 'constitution' not in title_lower:
            classification['type'] = 'ordinary_amendment'
            classification['confidence'] = 0.85
            classification['reasoning'].append('Title contains "amendment" but not "constitution"')
        
        # Rule 4: Constitutional act (not amendment)
        elif 'constitution' in title_lower and 'amendment' not in title_lower:
            classification['type'] = 'constitutional_act'
            classification['confidence'] = 0.80
            classification['constitutional_related'] = True
            classification['reasoning'].append('Title contains "constitution" but not "amendment"')
        
        # Rule 5: Year-based analysis
        if year:
            if year < 1956:  # Before Pakistan's first constitution
                classification['reasoning'].append(f'Year {year} predates Pakistan constitution')
                classification['confidence'] *= 0.9
            elif year == 1973:  # Current constitution year
                if 'constitution' in title_lower:
                    classification['confidence'] *= 1.1
                    classification['reasoning'].append('Year 1973 matches current constitution')
        
        # Rule 6: Text content analysis
        if text_content:
            # Check for constitutional references
            constitutional_terms = ['article', 'section', 'clause', 'schedule']
            constitutional_count = sum(1 for term in constitutional_terms if term in text_lower)
            
            if constitutional_count > 2:
                classification['constitutional_related'] = True
                classification['confidence'] *= 1.05
                classification['reasoning'].append(f'Contains {constitutional_count} constitutional terms')
        
        # Normalize confidence to 0-1 range
        classification['confidence'] = min(1.0, max(0.0, classification['confidence']))
        
        return classification
    
    def _should_use_gpt(self, rule_classification: Dict, title: str, year: Optional[int]) -> bool:
        """Determine if GPT analysis is needed"""
        if not self.enable_smart_filtering:
            return True
        
        # High confidence rule-based classification
        if rule_classification['confidence'] > 0.9:
            return False
        
        # Clear constitutional amendment
        if (rule_classification['type'] == 'constitutional_amendment' and 
            rule_classification['confidence'] > 0.8):
            return False
        
        # Complex cases that need GPT analysis
        if rule_classification['type'] == 'unknown':
            return True
        
        # Cases with mixed indicators
        if rule_classification['confidence'] < 0.7:
            return True
        
        return False
    
    def _calculate_confidence_score(self, rule_classification: Dict, title: str, year: Optional[int]) -> float:
        """Calculate overall confidence score"""
        base_confidence = rule_classification['confidence']
        
        # Adjust based on title clarity
        title_clarity = self._assess_title_clarity(title)
        base_confidence *= title_clarity
        
        # Adjust based on year consistency
        if year:
            year_consistency = self._assess_year_consistency(year, title)
            base_confidence *= year_consistency
        
        return min(1.0, max(0.0, base_confidence))
    
    def _assess_title_clarity(self, title: str) -> float:
        """Assess how clear and specific the title is"""
        if not title:
            return 0.5
        
        # Check for specific legal terms
        legal_terms = ['act', 'ordinance', 'order', 'amendment', 'constitution', 'bill']
        term_count = sum(1 for term in legal_terms if term.lower() in title.lower())
        
        # Check for year presence
        has_year = bool(re.search(r'\b(19|20)\d{2}\b', title))
        
        # Check for specific numbers or references
        has_numbers = bool(re.search(r'\b\d+\b', title))
        
        clarity_score = 0.5  # Base score
        
        if term_count > 0:
            clarity_score += 0.2 * min(term_count, 3)
        
        if has_year:
            clarity_score += 0.2
        
        if has_numbers:
            clarity_score += 0.1
        
        return min(1.0, clarity_score)
    
    def _assess_year_consistency(self, year: int, title: str) -> float:
        """Assess consistency between year and title content"""
        # Check if year makes sense for the title content
        title_lower = title.lower()
        
        if year < 1947:  # Before Pakistan independence
            if 'pakistan' in title_lower:
                return 0.7  # Suspicious
            else:
                return 1.0  # Normal for pre-independence acts
        
        elif year == 1973:
            if 'constitution' in title_lower:
                return 1.0  # Perfect match
            else:
                return 0.9  # Good year
        
        elif 1947 <= year <= 2024:
            return 1.0  # Reasonable year range
        
        else:
            return 0.5  # Future or very old year
    
    def _analyze_sections(self, statute: Dict) -> Dict:
        """Analyze sections for similarity and renumbering detection"""
        sections = statute.get('Sections', [])
        if not sections:
            return {'section_count': 0, 'similarity_analysis': {}}
        
        section_count = len(sections)
        similarity_analysis = {}
        
        # Extract section text for analysis
        section_texts = []
        for section in sections:
            if isinstance(section, dict):
                text = section.get('text', '') or section.get('content', '') or str(section)
            else:
                text = str(section)
            section_texts.append(text)
        
        # Analyze section similarities
        if len(section_texts) > 1:
            for i in range(len(section_texts)):
                for j in range(i + 1, len(section_texts)):
                    similarity = self._calculate_text_similarity(section_texts[i], section_texts[j])
                    key = f"section_{i+1}_vs_{j+1}"
                    similarity_analysis[key] = similarity
        
        return {
            'section_count': section_count,
            'section_texts': section_texts,
            'similarity_analysis': similarity_analysis,
            'average_similarity': np.mean(list(similarity_analysis.values())) if similarity_analysis else 0.0
        }
    
    def _calculate_text_similarity(self, text_a: str, text_b: str) -> float:
        """Calculate similarity between two text strings"""
        if not text_a or not text_b:
            return 0.0
        
        if text_a == text_b:
            return 1.0
        
        # Use rapidfuzz if available
        if RAPIDFUZZ_AVAILABLE:
            return fuzz.ratio(text_a, text_b) / 100.0
        
        # Fallback to difflib
        from difflib import SequenceMatcher
        return SequenceMatcher(None, text_a, text_b).ratio()
    
    def _check_year_discrepancy(self, title: str, year: Optional[int]) -> bool:
        """Check for year discrepancies in title"""
        if not year:
            return False
        
        # Look for other years mentioned in title
        title_years = re.findall(r'\b(19|20)\d{2}\b', title)
        
        if len(title_years) > 1:
            # Multiple years found
            years = [int(y) for y in title_years]
            if max(years) - min(years) > 10:  # Significant year difference
                return True
        
        return False
    
    def _analyze_title_similarity(self, title: str) -> float:
        """Analyze title similarity to known patterns"""
        if not title:
            return 0.0
        
        # Common title patterns
        patterns = [
            r'constitution.*amendment.*order.*\d{4}',
            r'constitution.*\d{4}',
            r'act.*\d{4}',
            r'ordinance.*\d{4}',
            r'amendment.*act.*\d{4}'
        ]
        
        title_lower = title.lower()
        pattern_matches = 0
        
        for pattern in patterns:
            if re.search(pattern, title_lower):
                pattern_matches += 1
        
        return min(1.0, pattern_matches / len(patterns))
    
    def _analyze_pair_relationship(self, result_a: PreprocessingResult, result_b: PreprocessingResult, 
                                 statute_a: Dict, statute_b: Dict):
        """Analyze relationship between two statutes"""
        # Check for obvious mismatches
        if result_a.rule_based_classification['constitutional_related'] != result_b.rule_based_classification['constitutional_related']:
            result_a.preprocessing_notes.append("Constitutional relationship mismatch detected")
            result_b.preprocessing_notes.append("Constitutional relationship mismatch detected")
        
        # Check year differences
        year_a = self._extract_year(statute_a.get('Statute_Name', ''))
        year_b = self._extract_year(statute_b.get('Statute_Name', ''))
        
        if year_a and year_b and abs(year_a - year_b) > 20:
            result_a.preprocessing_notes.append(f"Significant year difference: {year_a} vs {year_b}")
            result_b.preprocessing_notes.append(f"Significant year difference: {year_a} vs {year_b}")
    
    def get_cache_key(self, statute: Dict) -> str:
        """Generate cache key for statute"""
        title = statute.get('Statute_Name', '')
        year = self._extract_year(title)
        content_hash = hashlib.md5(self._extract_text_content(statute).encode()).hexdigest()[:8]
        
        return f"{title}_{year}_{content_hash}"
    
    def clear_cache(self):
        """Clear preprocessing cache"""
        self.cache.clear()
        self.rule_cache.clear()
    
    def get_statistics(self) -> Dict:
        """Get preprocessing statistics"""
        return {
            'cache_size': len(self.cache),
            'rule_cache_size': len(self.rule_cache),
            'language_detector': self.language_detector,
            'smart_filtering_enabled': self.enable_smart_filtering
        }
