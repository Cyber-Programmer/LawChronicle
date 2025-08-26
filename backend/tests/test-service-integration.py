"""
Integration tests for service-based endpoints

These tests validate the integration between service modules and API endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# Import the FastAPI app
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from main import app

client = TestClient(app)


class TestNormalizationServiceIntegration:
    """Test integration of NormalizationService with Phase2 endpoints"""
    
    def test_start_normalization_success(self):
        """Test new service-based normalization endpoint"""
        response = client.post(
            "/api/v1/phase2/start-normalization",
            json={
                "source_db": "test_source",
                "target_db": "test_target",
                "options": {"batch_size": 500}
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "timestamp" in data
        
        # Verify service configuration was returned
        result_data = data["data"]
        assert result_data["status"] == "configured"
        assert "validation" in result_data
        assert "config" in result_data
    
    def test_start_normalization_validation_error(self):
        """Test validation error handling"""
        response = client.post(
            "/api/v1/phase2/start-normalization",
            json={
                "source_db": "",  # Invalid: empty source
                "target_db": "test_target"
            }
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "error" in data["detail"]
        assert "Invalid input" in data["detail"]["error"]
    
    def test_start_normalization_same_database_error(self):
        """Test same database validation"""
        response = client.post(
            "/api/v1/phase2/start-normalization",
            json={
                "source_db": "same_db",
                "target_db": "same_db"  # Invalid: same as source
            }
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "Invalid input" in data["detail"]["error"]


class TestSectionSplittingServiceIntegration:
    """Test integration of SectionSplittingService with Phase3 endpoints"""
    
    def test_process_statute_success(self):
        """Test new service-based statute processing endpoint"""
        statute_data = {
            "_id": "test_statute_123",
            "statute_text": """1. Introduction
This is the introduction section.

2. Main Provisions  
These are the main provisions of the statute.

3. Final Provisions
These are the final provisions."""
        }
        
        response = client.post(
            "/api/v1/phase3/process-statute",
            json=statute_data
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "validation" in data
        
        # Verify processing results
        result_data = data["data"]
        assert result_data["status"] == "processed"
        assert result_data["original_id"] == "test_statute_123"
        assert len(result_data["sections"]) == 3
        assert "metadata" in result_data
        
        # Verify validation results
        validation = data["validation"]
        assert validation["valid"] is True
        assert validation["section_count"] == 3
    
    def test_process_statute_no_text(self):
        """Test error handling for missing statute text"""
        statute_data = {
            "_id": "test_statute_456"
            # Missing statute_text
        }
        
        response = client.post(
            "/api/v1/phase3/process-statute",
            json=statute_data
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "Invalid statute data" in data["detail"]["error"]
    
    def test_process_statute_empty_text(self):
        """Test handling of empty statute text"""
        statute_data = {
            "_id": "test_statute_789",
            "statute_text": ""
        }
        
        response = client.post(
            "/api/v1/phase3/process-statute",
            json=statute_data
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "Invalid statute data" in data["detail"]["error"]
    
    def test_process_statute_unsplit_text(self):
        """Test processing text with no section boundaries"""
        statute_data = {
            "_id": "test_statute_unsplit",
            "statute_text": "This is just plain text with no section markers or boundaries."
        }
        
        response = client.post(
            "/api/v1/phase3/process-statute",
            json=statute_data
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        # Should create one "unsplit" section
        sections = data["data"]["sections"]
        assert len(sections) == 1
        assert sections[0]["type"] == "unsplit"
        assert sections[0]["section_number"] == "1"
        assert sections[0]["section_title"] == "Full Text"


class TestServiceEndpointComparison:
    """Compare service-based endpoints with legacy endpoints"""
    
    def test_normalization_service_vs_legacy(self):
        """Compare new service endpoint response structure with legacy"""
        # Test new service endpoint
        service_response = client.post(
            "/api/v1/phase2/start-normalization",
            json={
                "source_db": "test_source",
                "target_db": "test_target"
            }
        )
        
        assert service_response.status_code == 200
        service_data = service_response.json()
        
        # Verify service response has expected structure
        assert "success" in service_data
        assert "message" in service_data
        assert "data" in service_data
        assert "timestamp" in service_data
        
        # Verify service data has normalization configuration
        assert "validation" in service_data["data"]
        assert "config" in service_data["data"]
        assert "next_steps" in service_data["data"]
    
    @patch('app.api.v1.endpoints.phase3.SectionSplittingService')
    def test_section_service_error_handling(self, mock_service_class):
        """Test error handling in section splitting service integration"""
        # Mock service to raise an exception
        mock_service = MagicMock()
        mock_service.process_statute.side_effect = Exception("Service error")
        mock_service_class.return_value = mock_service
        
        statute_data = {
            "_id": "test_error",
            "statute_text": "Some text"
        }
        
        response = client.post(
            "/api/v1/phase3/process-statute",
            json=statute_data
        )
        
        assert response.status_code == 500
        data = response.json()
        assert "Processing failed" in data["detail"]["error"]
        assert "Service error" in data["detail"]["message"]
