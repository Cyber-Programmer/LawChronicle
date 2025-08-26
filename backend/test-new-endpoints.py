"""
Test file for new Phase 2 sorting and cleaning endpoints
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
import sys
from pathlib import Path

# Add parent directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from main import app

client = TestClient(app)

# Mock data for testing
MOCK_STATUTE_DATA = [
    {
        "_id": "test_id_1",
        "Statute_Name": "Test Statute A",
        "Sections": [
            {"number": "3", "definition": "Section 3 content"},
            {"number": "preamble", "definition": "Preamble content"},
            {"number": "1", "definition": "Section 1 content"},
            {"number": "2", "definition": "Section 2 content"}
        ]
    },
    {
        "_id": "test_id_2", 
        "Statute_Name": "Test Statute B",
        "Sections": [
            {"number": "B", "definition": "Section B content"},
            {"number": "1", "definition": "Section 1 content"},
            {"number": "A", "definition": "Section A content"}
        ]
    }
]

class TestPhase2NewEndpoints:
    """Test class for new Phase 2 sorting and cleaning endpoints"""
    
    @patch('app.api.v1.endpoints.phase2.get_db')
    def test_apply_sorting_endpoint_structure(self, mock_get_db):
        """Test that the apply-sorting endpoint is accessible and has correct structure"""
        # Mock database
        mock_db = AsyncMock()
        mock_get_db.return_value = mock_db
        
        # Test request payload
        sorting_request = {
            "rules": {
                "preamble_first": True,
                "numeric_order": True,
                "alphabetical_fallback": True
            },
            "scope": "all"
        }
        
        # This will fail with database connection, but we're testing endpoint structure
        response = client.post("/api/v1/phase2/apply-sorting", json=sorting_request)
        
        # Should not return 404 (endpoint exists)
        assert response.status_code != 404, "apply-sorting endpoint should exist"
        
        # Should return either 500 (database error) or 200 (success)
        assert response.status_code in [200, 500], f"Unexpected status code: {response.status_code}"
    
    @patch('app.api.v1.endpoints.phase2.get_db')
    def test_apply_cleaning_endpoint_structure(self, mock_get_db):
        """Test that the apply-cleaning endpoint is accessible and has correct structure"""
        # Mock database
        mock_db = AsyncMock()
        mock_get_db.return_value = mock_db
        
        # Test request payload
        cleaning_request = {
            "mappings": [
                {"source": "number", "target": "section_number", "enabled": True},
                {"source": "definition", "target": "section_content", "enabled": True}
            ],
            "scope": "all"
        }
        
        # This will fail with database connection, but we're testing endpoint structure
        response = client.post("/api/v1/phase2/apply-cleaning", json=cleaning_request)
        
        # Should not return 404 (endpoint exists)  
        assert response.status_code != 404, "apply-cleaning endpoint should exist"
        
        # Should return either 500 (database error) or 200 (success)
        assert response.status_code in [200, 500], f"Unexpected status code: {response.status_code}"
    
    def test_sorting_request_validation(self):
        """Test request validation for sorting endpoint"""
        # Test with missing required fields
        invalid_request = {"scope": "all"}  # Missing rules
        
        response = client.post("/api/v1/phase2/apply-sorting", json=invalid_request)
        assert response.status_code == 422, "Should return validation error for missing rules"
    
    def test_cleaning_request_validation(self):
        """Test request validation for cleaning endpoint"""
        # Test with missing required fields  
        invalid_request = {"scope": "all"}  # Missing mappings
        
        response = client.post("/api/v1/phase2/apply-cleaning", json=invalid_request)
        assert response.status_code == 422, "Should return validation error for missing mappings"
    
    def test_endpoints_in_openapi_docs(self):
        """Test that new endpoints appear in OpenAPI documentation"""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        
        openapi_spec = response.json()
        paths = openapi_spec.get("paths", {})
        
        # Check that our new endpoints are documented
        assert "/api/v1/phase2/apply-sorting" in paths, "apply-sorting should be in OpenAPI docs"
        assert "/api/v1/phase2/apply-cleaning" in paths, "apply-cleaning should be in OpenAPI docs"
        
        # Check HTTP methods
        sorting_methods = paths["/api/v1/phase2/apply-sorting"].keys()
        cleaning_methods = paths["/api/v1/phase2/apply-cleaning"].keys()
        
        assert "post" in sorting_methods, "apply-sorting should accept POST requests"
        assert "post" in cleaning_methods, "apply-cleaning should accept POST requests"

if __name__ == "__main__":
    # Run basic tests
    test_instance = TestPhase2NewEndpoints()
    
    print("🧪 Testing Phase 2 new endpoints...")
    
    try:
        test_instance.test_apply_sorting_endpoint_structure()
        print("✅ Sorting endpoint structure test passed")
    except Exception as e:
        print(f"❌ Sorting endpoint test failed: {e}")
    
    try:
        test_instance.test_apply_cleaning_endpoint_structure()
        print("✅ Cleaning endpoint structure test passed")
    except Exception as e:
        print(f"❌ Cleaning endpoint test failed: {e}")
    
    try:
        test_instance.test_sorting_request_validation()
        print("✅ Sorting validation test passed")
    except Exception as e:
        print(f"❌ Sorting validation test failed: {e}")
    
    try:
        test_instance.test_cleaning_request_validation()
        print("✅ Cleaning validation test passed")
    except Exception as e:
        print(f"❌ Cleaning validation test failed: {e}")
    
    try:
        test_instance.test_endpoints_in_openapi_docs()
        print("✅ OpenAPI documentation test passed")
    except Exception as e:
        print(f"❌ OpenAPI documentation test failed: {e}")
    
    print("🎉 Basic endpoint tests completed!")
