"""
Phase 3 Section Splitting Service  

Extracts section splitting and field cleaning logic into testable service modules.
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import re
import logging
import json
import os
from pathlib import Path
from openai import AzureOpenAI

logger = logging.getLogger(__name__)

# Load Azure OpenAI configuration
_cfg_path = Path(__file__).resolve().parent.parent.parent / 'config' / 'azure_openai_config.json'
_aoai_client = None

if _cfg_path.exists():
    try:
        _cfg = json.load(open(_cfg_path, 'r', encoding='utf-8'))
        azure_config = _cfg.get('azure_openai', {})
        api_key = azure_config.get('api_key')
        endpoint = azure_config.get('endpoint')
        
        # Only initialize if we have real credentials (not placeholder values)
        if api_key and endpoint and api_key != "your-azure-openai-api-key-here":
            _aoai_client = AzureOpenAI(
                api_key=api_key,
                api_version=azure_config.get('api_version', '2024-11-01-preview'),
                azure_endpoint=endpoint
            )
            logger.info("Azure OpenAI client initialized successfully")
        else:
            logger.warning("Azure OpenAI credentials not configured - AI features will be disabled")
    except Exception as e:
        logger.warning(f"Failed to initialize Azure OpenAI client: {e}")
        _aoai_client = None
else:
    logger.warning("Azure OpenAI config file not found - AI features will be disabled")


class SectionSplittingEngine:
    """Core section splitting business logic"""
    
    def __init__(self):
        self.section_patterns = [
            r'^\d+\.',  # Numbered sections: "1.", "2.", etc.
            r'^Section\s+\d+',  # "Section 1", "Section 2", etc.
            r'^§\s*\d+',  # "§ 1", "§2", etc.
            r'^\(\d+\)',  # "(1)", "(2)", etc.
            r'^[A-Z]\.',  # "A.", "B.", etc.
        ]
    
    def detect_section_boundaries(self, text: str) -> List[Tuple[int, str]]:
        """Detect potential section boundaries in text"""
        boundaries = []
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            if not line_stripped:
                continue
                
            for pattern in self.section_patterns:
                if re.match(pattern, line_stripped, re.IGNORECASE):
                    boundaries.append((i, line_stripped))
                    break
                    
        return boundaries
    
    def split_into_sections(self, text: str) -> List[Dict[str, Any]]:
        """Split text into logical sections"""
        boundaries = self.detect_section_boundaries(text)
        
        if not boundaries:
            return [{
                "section_number": "1",
                "section_title": "Full Text",
                "content": text.strip(),
                "type": "unsplit"
            }]
        
        sections = []
        lines = text.split('\n')
        
        for i, (line_num, boundary_line) in enumerate(boundaries):
            # Determine section content
            start_line = line_num
            end_line = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(lines)
            
            section_lines = lines[start_line:end_line]
            content = '\n'.join(section_lines).strip()
            
            # Extract section number/title
            section_info = self._parse_section_header(boundary_line)
            
            sections.append({
                "section_number": section_info["number"],
                "section_title": section_info["title"],
                "content": content,
                "type": "split",
                "line_start": start_line,
                "line_end": end_line
            })
            
        return sections
    
    def _parse_section_header(self, header_line: str) -> Dict[str, str]:
        """Parse section header to extract number and title"""
        # Simple parsing - can be enhanced
        header = header_line.strip()
        
        # Try to extract number
        number_match = re.search(r'\d+', header)
        number = number_match.group() if number_match else "1"
        
        # Title is everything after the number/marker
        title_match = re.search(r'^[^a-zA-Z]*(.+)$', header)
        title = title_match.group(1).strip() if title_match else header
        
        return {
            "number": number,
            "title": title
        }


class FieldCleaningEngine:
    """Field cleaning and validation logic"""
    
    def __init__(self):
        self.cleaning_rules = {
            "text_fields": ["remove_extra_whitespace", "normalize_quotes", "fix_encoding"],
            "date_fields": ["parse_dates", "validate_ranges", "standardize_format"],
            "numeric_fields": ["extract_numbers", "validate_ranges"]
        }
    
    def clean_text_field(self, text: str) -> str:
        """Clean and normalize text field"""
        if not text or not isinstance(text, str):
            return ""
            
        # Remove extra whitespace
        cleaned = re.sub(r'\s+', ' ', text.strip())
        
        # Normalize quotes
        cleaned = cleaned.replace('"', '"').replace('"', '"')
        cleaned = cleaned.replace(''', "'").replace(''', "'")
        
        # Remove control characters
        cleaned = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', cleaned)
        
        return cleaned
    
    def validate_date_field(self, date_str: str) -> Optional[Dict[str, Any]]:
        """Validate and parse date field"""
        if not date_str:
            return None
            
        try:
            from dateutil import parser
            parsed_date = parser.parse(date_str, fuzzy=True)
            
            # Basic validation - dates should be reasonable for legal documents
            if parsed_date.year < 1800 or parsed_date.year > 2030:
                return {
                    "valid": False,
                    "error": f"Date year {parsed_date.year} out of reasonable range",
                    "original": date_str
                }
            
            return {
                "valid": True,
                "parsed": parsed_date.isoformat(),
                "original": date_str
            }
            
        except (ValueError, TypeError) as e:
            return {
                "valid": False,
                "error": str(e),
                "original": date_str
            }
    
    def extract_metadata(self, sections: List[Dict]) -> Dict[str, Any]:
        """Extract metadata from split sections"""
        metadata = {
            "total_sections": len(sections),
            "section_types": {},
            "content_stats": {
                "total_length": 0,
                "avg_section_length": 0,
                "longest_section": 0,
                "shortest_section": float('inf')
            },
            "extracted_at": datetime.now().isoformat()
        }
        
        for section in sections:
            # Count section types
            section_type = section.get("type", "unknown")
            metadata["section_types"][section_type] = metadata["section_types"].get(section_type, 0) + 1
            
            # Calculate content stats
            content_length = len(section.get("content", ""))
            metadata["content_stats"]["total_length"] += content_length
            metadata["content_stats"]["longest_section"] = max(
                metadata["content_stats"]["longest_section"], content_length
            )
            metadata["content_stats"]["shortest_section"] = min(
                metadata["content_stats"]["shortest_section"], content_length
            )
        
        if sections:
            metadata["content_stats"]["avg_section_length"] = (
                metadata["content_stats"]["total_length"] / len(sections)
            )
        
        return metadata


class SectionSplittingService:
    def validate_pakistan_law_only(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Only validate Pakistan law, do not split or clean."""
        from app.api.v1.endpoints.phase3 import FieldCleaningEngine
        is_pak = FieldCleaningEngine.validate_pakistan_law(doc)
        reason = None
        # Rule-based checks for concise reasons
        if not is_pak:
            # Pre-1947 check
            date_str = doc.get("Date", "")
            try:
                from dateutil import parser
                dt = parser.parse(date_str, fuzzy=True, dayfirst=True)
                if dt.year < 1947:
                    reason = "Pre-1947"
            except Exception:
                pass
            # Foreign statute check
            statute_name = doc.get("Statute_Name", "").lower()
            preamble = doc.get("Preamble", "").lower()
            foreign_keywords = [
                "india", "indian", "uk", "united kingdom", "england", "scotland", "wales", "ireland",
                "united states", "usa", "america", "bangladesh", "sri lanka", "nepal", "afghanistan", "iran",
                "china", "russia", "turkey", "turkish", "malaysia", "canada", "australia", "france", "germany",
                "japan", "italy", "spain", "sweden", "norway", "denmark", "netherlands", "switzerland", "belgium",
                "brazil", "mexico", "south africa", "egypt", "indonesia", "thailand"
            ]
            if any(kw in statute_name or kw in preamble for kw in foreign_keywords):
                reason = "Foreign statute"
                # Check for Pakistan mention in other fields (conservative check)
                def contains_pakistan_or_province(*fields):
                    keywords = ["pakistan"] + [p.lower() for p in [
                        'Azad Kashmir And Jammu', 'Balochistan', 'Federal', 'Khyber Pakhtunkhwa', 'Punjab', 'Sindh'
                    ]]
                    for f in fields:
                        if not f:
                            continue
                        fl = f.lower()
                        for kw in keywords:
                            if kw in fl:
                                return True
                    return False

                if contains_pakistan_or_province(statute_name, preamble, doc.get('Province', '')):
                    # Treat as Pakistan law if any positive signal found
                    is_pak = True
                # Fallback to GPT if available and still uncertain
                if not reason and not is_pak:
                    try:
                        from pathlib import Path
                        import json
                        from openai import AzureOpenAI
                        _cfg_path = Path(__file__).resolve().parent.parent.parent / 'config' / 'azure_openai_config.json'
                        if _cfg_path.exists():
                            _cfg = json.load(open(_cfg_path, 'r', encoding='utf-8'))
                            _aoai_client = AzureOpenAI(
                                api_key=_cfg.get('azure_openai_api_key'),
                                api_version=_cfg.get('azure_openai_api_version'),
                                azure_endpoint=_cfg.get('azure_openai_endpoint')
                            )
                            system_prompt = (
                                "You are a legal expert on the Pakistani legal system. "
                                "In one or two words, state the reason why this statute is NOT a Pakistan law (e.g., 'Foreign statute', 'Pre-1947', 'Rule-based failed'). "
                                "If it is a Pakistan law, reply 'Pakistan law'."
                            )
                            user_prompt = f"Preamble: {preamble}\nDate: {date_str}\nStatute Name: {statute_name}\n"
                            resp = _aoai_client.chat.completions.create(
                                model=_cfg.get('azure_openai_deployment'),
                                messages=[
                                    {"role": "system", "content": system_prompt},
                                    {"role": "user", "content": user_prompt}
                                ],
                                temperature=0.2
                            )
                            content = resp.choices[0].message.content.strip()
                            if content.lower().startswith('pakistan law'):
                                is_pak = True
                            else:
                                reason = content
                    except Exception as e:
                        reason = f"GPT error: {e}"
        return {
            "is_pakistan_law": is_pak,
            "reason": reason or "Unknown reason"
        }
    """High-level service for section splitting workflow"""
    
    def __init__(self):
        self.splitter = SectionSplittingEngine()
        self.cleaner = FieldCleaningEngine()
    
    def process_statute(self, statute_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single statute through splitting and cleaning, dropping non-Pakistan laws"""
        try:
            # Pakistan law validation (drop non-Pakistan laws)
            # Pakistan law validation: rule-based first, then GPT fallback
            from app.api.v1.endpoints.phase3 import FieldCleaningEngine
            is_pak = FieldCleaningEngine.validate_pakistan_law(statute_data)
            if not is_pak:
                # Fallback to GPT if client configured
                if _aoai_client:
                    preamble = statute_data.get('Preamble', '')
                    name = statute_data.get('Statute_Name', '')
                    date_str = statute_data.get('Date', '')
                    system_prompt = (
                        "You are a legal expert on the Pakistani legal system. "
                        "Answer Yes or No whether this statute relates to Pakistan law."
                    )
                    user_prompt = f"Preamble: {preamble}\nDate: {date_str}\nStatute Name: {name}\n"
                    try:
                        resp = _aoai_client.chat.completions.create(
                            model=_cfg.get('azure_openai_deployment'),
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_prompt}
                            ],
                            temperature=0.2
                        )
                        content = resp.choices[0].message.content.strip().lower()
                        if content.startswith('yes'):
                            is_pak = True
                    except Exception as _e:
                        logger.warning(f"GPT validation failed: {_e}")
                if not is_pak:
                    logger.info("Dropping non-Pakistan law during processing.")
                    return {
                        "status": "dropped",
                        "reason": "Non-Pakistan law",
                        "original_id": statute_data.get("_id"),
                        "processed_at": datetime.now().isoformat()
                    }

            # Build main_text from Sections[*].Statute for any statute that wasn't dropped
            main_text = ""
            sections_list = statute_data.get("Sections", None)
            if not isinstance(sections_list, list) or not sections_list:
                raise ValueError("Sections array missing or empty in input data")
            main_text = "\n\n".join(
                s.get("Statute", "") for s in sections_list if s.get("Statute")
            )
            if not main_text:
                raise ValueError("No Statute found in Sections array of input data")
            # Split into sections
            sections = self.splitter.split_into_sections(main_text)
            # Clean each section
            for section in sections:
                section["content"] = self.cleaner.clean_text_field(section["content"])
                section["section_title"] = self.cleaner.clean_text_field(section["section_title"])
            # Extract metadata
            metadata = self.cleaner.extract_metadata(sections)
            return {
                "status": "processed",
                "original_id": statute_data.get("_id"),
                "sections": sections,
                "metadata": metadata,
                "processed_at": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to process statute: {e}")
            raise
    
    def validate_processing_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate processing results"""
        issues = []
        
        sections = result.get("sections", [])
        if not sections:
            issues.append("No sections generated")
        
        for i, section in enumerate(sections):
            if not section.get("content", "").strip():
                issues.append(f"Section {i+1} has no content")
            
            if not section.get("section_number"):
                issues.append(f"Section {i+1} missing section number")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "section_count": len(sections),
            "validated_at": datetime.now().isoformat()
        }
