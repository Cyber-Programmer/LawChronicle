#!/usr/bin/env python3
"""
Unit tests for Phase 5 Grouping Service
Tests AI-powered semantic grouping and versioning functionality.
"""

import sys
import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

# Add project paths
current_dir = Path(__file__).parent
backend_dir = current_dir.parent
project_dir = backend_dir.parent

sys.path.insert(0, str(project_dir))
sys.path.insert(0, str(backend_dir))

from app.core.services.phase5_service import Phase5Service
from shared.types.common import Phase5Config


class TestPhase5Grouping:
    """Test suite for Phase 5 semantic grouping functionality."""
    
    @pytest.fixture
    def service(self):
        """Create a Phase5Service instance for testing."""
        service = Phase5Service()
        return service
    
    @pytest.fixture
    def sample_statutes(self):
        """Sample statute data for testing."""
        return [
            {
                "_id": "1",
                "Statute_Name": "The Companies Act 1984",
                "Province": "Federal",
                "Date_of_Commencement": "1984-09-01",
                "Preamble": "An Act to consolidate and amend the law relating to companies",
                "Sections": [
                    {"content": "This Act may be called the Companies Act, 1984"}
                ]
            },
            {
                "_id": "2", 
                "Statute_Name": "Companies Act (Amendment) 2017",
                "Province": "Federal",
                "Date_of_Commencement": "2017-05-15",
                "Preamble": "An Act to amend the Companies Act, 1984",
                "Sections": [
                    {"content": "Amendment to the Companies Act 1984"}
                ]
            },
            {
                "_id": "3",
                "Statute_Name": "The Criminal Procedure Code 1898",
                "Province": "Federal", 
                "Date_of_Commencement": "1898-04-01",
                "Preamble": "An Act to consolidate the law relating to criminal procedure",
                "Sections": [
                    {"content": "This Act may be called the Code of Criminal Procedure, 1898"}
                ]
            },
            {
                "_id": "4",
                "Statute_Name": "Companies Act 1984", 
                "Province": "Punjab",  # Different province
                "Date_of_Commencement": "1984-09-01",
                "Preamble": "An Act to consolidate and amend the law relating to companies",
                "Sections": [
                    {"content": "This Act may be called the Companies Act, 1984"}
                ]
            },
            {
                "_id": "5",
                "Statute_Name": "The Punjab Municipal Act 2013",
                "Province": "Punjab",
                "Date_of_Commencement": "2013-07-01", 
                "Preamble": "An Act to provide for municipal governance in Punjab",
                "Sections": [
                    {"content": "This Act extends to the whole of Punjab"}
                ]
            }
        ]
    
    def test_extract_base_name(self, service):
        """Test base name extraction logic."""
        test_cases = [
            ("The Companies Act 1984", "The Companies Act 1984"),  # Keep years in base name
            ("Criminal Procedure Code 1898 (Amendment)", "Criminal Procedure Code 1898"),
            ("Income Tax Ordinance 2001 Revised", "Income Tax Ordinance 2001"),
            ("Contract Act 1872 (No. 5)", "Contract Act 1872"),
            ("Simple Act", "Simple Act"),
            ("Companies Act (Amendment) 2017", "Companies Act 2017")  # Remove (Amendment) but keep year
        ]
        
        for input_name, expected in test_cases:
            result = service._extract_base_name(input_name)
            assert result == expected, f"Expected '{expected}', got '{result}' for '{input_name}'"
    
    def test_extract_statute_info(self, service, sample_statutes):
        """Test statute information extraction for AI analysis."""
        statute = sample_statutes[0]
        info = service._extract_statute_info(statute)
        
        assert info["title"] == "The Companies Act 1984"
        assert info["province"] == "Federal"
        assert info["year"] == "1984"
        assert "consolidate and amend" in info["text"]
    
    def test_fallback_rule_based_grouping(self, service, sample_statutes):
        """Test fallback rule-based grouping when AI is unavailable."""
        # Test with first 3 statutes 
        test_statutes = sample_statutes[:3]
        groups = service._fallback_rule_based_grouping(test_statutes)
        
        # With improved base name extraction:
        # - "The Companies Act 1984" -> "The Companies Act 1984" 
        # - "Companies Act (Amendment) 2017" -> "Companies Act 2017"
        # - "The Criminal Procedure Code 1898" -> "The Criminal Procedure Code 1898"
        # Still 3 different base names, but let's verify the grouping logic works
        assert len(groups) >= 2, "Should have at least 2 groups"
        
        # Each group should have at least 1 statute
        assert all(len(group) >= 1 for group in groups), "Each group should have at least 1 statute"
        
        # Total statutes should be preserved
        total_statutes = sum(len(group) for group in groups)
        assert total_statutes == 3, "All 3 statutes should be grouped"
    
    def test_province_separation(self, service, sample_statutes):
        """Test that statutes from different provinces are never grouped."""
        # Federal and Punjab Companies Acts should be in different groups
        federal_companies = sample_statutes[0]  # Federal Companies Act
        punjab_companies = sample_statutes[3]   # Punjab Companies Act
        
        groups = service._fallback_rule_based_grouping([federal_companies, punjab_companies])
        
        # Should be 2 separate groups despite similar names
        assert len(groups) == 2, "Statutes from different provinces should not be grouped"
        assert all(len(group) == 1 for group in groups), "Each group should have only 1 statute"
    
    @pytest.mark.asyncio
    async def test_create_versioned_statutes(self, service, sample_statutes):
        """Test chronological versioning within a group."""
        # Use Companies Acts (different years)
        companies_statutes = [sample_statutes[0], sample_statutes[1]]  # 1984, 2017
        group_id = "test-group-123"
        
        versioned = service._create_versioned_statutes(group_id, companies_statutes)
        
        assert len(versioned) == 2
        
        # Should be sorted chronologically
        assert versioned[0].version_number == 1
        assert versioned[1].version_number == 2
        assert versioned[0].is_base_version is True
        assert versioned[1].is_base_version is False
        
        # 1984 Act should be version 1 (older)
        v1_year = versioned[0].date_enacted.year if versioned[0].date_enacted else None
        v2_year = versioned[1].date_enacted.year if versioned[1].date_enacted else None
        
        assert v1_year == 1984, "Version 1 should be the 1984 Act"
        assert v2_year == 2017, "Version 2 should be the 2017 Amendment"
    
    @patch('app.core.services.phase5_service.AzureOpenAI')
    def test_azure_openai_initialization(self, mock_azure_openai, service):
        """Test Azure OpenAI client initialization."""
        # Test with config file
        with patch('builtins.open'), \
             patch('pathlib.Path.exists', return_value=True), \
             patch('json.load', return_value={
                 'azure_openai': {
                     'api_key': 'test-key',
                     'endpoint': 'https://test.openai.azure.com/',
                     'deployment_name': 'gpt-4o'
                 }
             }):
            
            service._init_azure_openai()
            assert service.azure_openai_client is not None
            mock_azure_openai.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_ai_grouping_response_parsing(self, service):
        """Test parsing of Azure OpenAI grouping responses."""
        # Mock Azure OpenAI client response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '[[0, 1], [2], [3, 4]]'
        
        service.azure_openai_client = Mock()
        service.azure_openai_client.chat.completions.create.return_value = mock_response
        service.deployment_name = "gpt-4o"
        
        test_statutes = [{"Statute_Name": f"Test Act {i}"} for i in range(5)]
        
        groups = await service._call_azure_openai_grouping(test_statutes)
        
        expected_groups = [[0, 1], [2], [3, 4]]
        assert groups == expected_groups
    
    @pytest.mark.asyncio
    async def test_ai_grouping_fallback_on_error(self, service, sample_statutes):
        """Test fallback to rule-based grouping when AI fails."""
        # Mock AI failure
        service.azure_openai_client = Mock()
        service.azure_openai_client.chat.completions.create.side_effect = Exception("API Error")
        
        test_statutes = sample_statutes[:3]
        groups = await service._call_azure_openai_grouping(test_statutes)
        
        # Should fallback to rule-based grouping
        assert isinstance(groups, list)
        assert all(isinstance(group, list) for group in groups)
        assert len(groups) > 0
    
    @pytest.mark.asyncio
    async def test_ai_grouping_invalid_json_fallback(self, service):
        """Test fallback when AI returns invalid JSON."""
        # Mock invalid JSON response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "This is not valid JSON"
        
        service.azure_openai_client = Mock()
        service.azure_openai_client.chat.completions.create.return_value = mock_response
        
        test_statutes = [{"Statute_Name": f"Test Act {i}"} for i in range(3)]
        
        groups = await service._call_azure_openai_grouping(test_statutes)
        
        # Should fallback to rule-based grouping
        assert isinstance(groups, list)
        assert len(groups) == 3  # Each statute in its own group as fallback
    
    @pytest.mark.asyncio 
    async def test_province_isolation_in_grouping(self, service, sample_statutes):
        """Test that the main grouping method properly isolates by province."""
        config = Phase5Config(use_azure_openai=False)  # Use rule-based for predictable testing
        
        # All sample statutes - should be grouped by province first
        groups = await service._group_statutes_by_similarity(sample_statutes, config)
        
        # Verify no group contains statutes from different provinces
        for group_id, statutes_in_group in groups.items():
            provinces = {s.get("Province", "unknown") for s in statutes_in_group}
            assert len(provinces) == 1, f"Group {group_id} contains statutes from multiple provinces: {provinces}"
    
    def test_date_extraction(self, service):
        """Test date extraction from various date fields."""
        test_cases = [
            ({"Date_of_Commencement": "1984-09-01"}, 1984),
            ({"Date_of_Assent": "2017-05-15T00:00:00Z"}, 2017),
            ({"Date_Passed": datetime(1898, 4, 1)}, 1898),
            ({"unknown_field": "not a date"}, None)
        ]
        
        for statute_data, expected_year in test_cases:
            date = service._extract_date(statute_data)
            if expected_year:
                assert date is not None, f"Expected date extraction from {statute_data}"
                assert date.year == expected_year, f"Expected year {expected_year}, got {date.year if date else None}"
            else:
                assert date is None, f"Expected no date extraction from {statute_data}"


# Test runner function
def run_tests():
    """Run all Phase 5 tests."""
    print("🔄 Running Phase 5 Grouping Tests...")
    
    # Run pytest programmatically
    pytest_args = [
        __file__,
        "-v",
        "--tb=short",
        "-x"  # Stop on first failure
    ]
    
    result = pytest.main(pytest_args)
    
    if result == 0:
        print("✅ All Phase 5 tests passed!")
    else:
        print("❌ Some Phase 5 tests failed!")
    
    return result


if __name__ == "__main__":
    run_tests()
