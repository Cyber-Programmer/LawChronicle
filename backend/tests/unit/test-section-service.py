"""
Unit tests for SectionSplittingService

These tests validate the section splitting and field cleaning logic extracted from phase3.
"""

import pytest
from datetime import datetime

from app.core.services.section_service import (
    SectionSplittingEngine,
    FieldCleaningEngine,
    SectionSplittingService
)


class TestSectionSplittingEngine:
    
    def test_detect_section_boundaries_numbered(self):
        engine = SectionSplittingEngine()
        text = """1. First section content
Some content here
2. Second section content
More content here"""
        
        boundaries = engine.detect_section_boundaries(text)
        
        assert len(boundaries) == 2
        assert boundaries[0][1] == "1. First section content"
        assert boundaries[1][1] == "2. Second section content"
    
    def test_detect_section_boundaries_no_sections(self):
        engine = SectionSplittingEngine()
        text = "Just plain text with no section markers"
        
        boundaries = engine.detect_section_boundaries(text)
        
        assert len(boundaries) == 0
    
    def test_split_into_sections_with_boundaries(self):
        engine = SectionSplittingEngine()
        text = """1. First section
Content of first section
2. Second section  
Content of second section"""
        
        sections = engine.split_into_sections(text)
        
        assert len(sections) == 2
        assert sections[0]["section_number"] == "1"
        assert sections[0]["type"] == "split"
        assert "First section" in sections[0]["content"]
        assert sections[1]["section_number"] == "2"
    
    def test_split_into_sections_no_boundaries(self):
        engine = SectionSplittingEngine()
        text = "Just plain text content"
        
        sections = engine.split_into_sections(text)
        
        assert len(sections) == 1
        assert sections[0]["section_number"] == "1"
        assert sections[0]["type"] == "unsplit"
        assert sections[0]["content"] == text
    
    def test_parse_section_header(self):
        engine = SectionSplittingEngine()
        
        result = engine._parse_section_header("1. Introduction")
        assert result["number"] == "1"
        assert result["title"] == "Introduction"
        
        result = engine._parse_section_header("Section 42")
        assert result["number"] == "42"
        assert result["title"] == "Section 42"


class TestFieldCleaningEngine:
    
    def test_clean_text_field_normal(self):
        engine = FieldCleaningEngine()
        
        dirty_text = "  This  has   extra    spaces  and\nnewlines  "
        cleaned = engine.clean_text_field(dirty_text)
        
        assert cleaned == "This has extra spaces and newlines"
    
    def test_clean_text_field_quotes(self):
        engine = FieldCleaningEngine()
        
        text_with_quotes = 'He said "Hello" and \'goodbye\''
        cleaned = engine.clean_text_field(text_with_quotes)
        
        assert '"' in cleaned and "'" in cleaned
    
    def test_clean_text_field_empty(self):
        engine = FieldCleaningEngine()
        
        assert engine.clean_text_field("") == ""
        assert engine.clean_text_field(None) == ""
        assert engine.clean_text_field("   ") == ""
    
    def test_validate_date_field_valid(self):
        engine = FieldCleaningEngine()
        
        result = engine.validate_date_field("2023-01-15")
        
        assert result["valid"] is True
        assert "2023-01-15" in result["parsed"]
        assert result["original"] == "2023-01-15"
    
    def test_validate_date_field_invalid_year(self):
        engine = FieldCleaningEngine()
        
        result = engine.validate_date_field("1700-01-01")
        
        assert result["valid"] is False
        assert "out of reasonable range" in result["error"]
    
    def test_validate_date_field_unparseable(self):
        engine = FieldCleaningEngine()
        
        result = engine.validate_date_field("not a date")
        
        assert result["valid"] is False
        assert "error" in result
    
    def test_validate_date_field_empty(self):
        engine = FieldCleaningEngine()
        
        result = engine.validate_date_field("")
        
        assert result is None
    
    def test_extract_metadata(self):
        engine = FieldCleaningEngine()
        
        sections = [
            {"type": "split", "content": "Short"},
            {"type": "split", "content": "This is longer content"},
            {"type": "unsplit", "content": "Medium length"}
        ]
        
        metadata = engine.extract_metadata(sections)
        
        assert metadata["total_sections"] == 3
        assert metadata["section_types"]["split"] == 2
        assert metadata["section_types"]["unsplit"] == 1
        assert metadata["content_stats"]["total_length"] > 0
        assert metadata["content_stats"]["avg_section_length"] > 0
        assert "extracted_at" in metadata


class TestSectionSplittingService:
    
    def test_process_statute_success(self):
        service = SectionSplittingService()
        
        statute_data = {
            "_id": "test_id",
            "statute_text": """1. First section content
This is the first section.
2. Second section content
This is the second section."""
        }
        
        result = service.process_statute(statute_data)
        
        assert result["status"] == "processed"
        assert result["original_id"] == "test_id"
        assert len(result["sections"]) == 2
        assert "metadata" in result
        assert "processed_at" in result
    
    def test_process_statute_no_text(self):
        service = SectionSplittingService()
        
        statute_data = {"_id": "test_id"}
        
        with pytest.raises(ValueError, match="No statute_text found"):
            service.process_statute(statute_data)
    
    def test_validate_processing_result_valid(self):
        service = SectionSplittingService()
        
        result = {
            "sections": [
                {"section_number": "1", "content": "Valid content"},
                {"section_number": "2", "content": "More valid content"}
            ]
        }
        
        validation = service.validate_processing_result(result)
        
        assert validation["valid"] is True
        assert len(validation["issues"]) == 0
        assert validation["section_count"] == 2
    
    def test_validate_processing_result_no_sections(self):
        service = SectionSplittingService()
        
        result = {"sections": []}
        
        validation = service.validate_processing_result(result)
        
        assert validation["valid"] is False
        assert "No sections generated" in validation["issues"]
    
    def test_validate_processing_result_empty_content(self):
        service = SectionSplittingService()
        
        result = {
            "sections": [
                {"section_number": "1", "content": ""},
                {"section_number": "", "content": "Valid content"}
            ]
        }
        
        validation = service.validate_processing_result(result)
        
        assert validation["valid"] is False
        assert len(validation["issues"]) == 2  # Empty content + missing section number
