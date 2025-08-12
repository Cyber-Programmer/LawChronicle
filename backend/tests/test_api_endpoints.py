import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import json
from datetime import datetime

# Import the FastAPI app
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from main import app

client = TestClient(app)

class TestAuthenticationEndpoints:
    """Test cases for authentication endpoints"""
    
    def test_login_success(self):
        """Test successful login with valid credentials"""
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "admin",
                "password": "admin123",
                "grant_type": "password"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "access_token" in data["data"]
        assert data["data"]["token_type"] == "bearer"
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "invalid",
                "password": "wrong",
                "grant_type": "password"
            }
        )
        assert response.status_code == 401
    
    def test_get_current_user_with_token(self):
        """Test getting current user with valid token"""
        # First login to get token
        login_response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "admin",
                "password": "admin123",
                "grant_type": "password"
            }
        )
        token = login_response.json()["data"]["access_token"]
        
        # Use token to get user info
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
    
    def test_logout(self):
        """Test logout endpoint"""
        response = client.post("/api/v1/auth/logout")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

class TestDatabaseEndpoints:
    """Test cases for database endpoints"""
    
    @patch('pymongo.MongoClient')
    def test_database_connect_success(self, mock_client):
        """Test successful database connection"""
        mock_client.return_value.admin.command.return_value = {"ok": 1}
        mock_client.return_value.__getitem__.return_value.__getitem__.return_value.count_documents.return_value = 100
        
        response = client.post(
            "/api/v1/database/connect",
            json={
                "connection_string": "mongodb://localhost:27017",
                "database_name": "test_db",
                "test_connection": True
            }
        )
        assert response.status_code == 200
    
    @patch('pymongo.MongoClient')
    def test_database_connect_failure(self, mock_client):
        """Test database connection failure"""
        mock_client.side_effect = Exception("Connection failed")
        
        response = client.post(
            "/api/v1/database/connect",
            json={
                "connection_string": "mongodb://invalid:27017",
                "database_name": "test_db",
                "test_connection": True
            }
        )
        assert response.status_code == 422

class TestPhase1Endpoints:
    """Test cases for Phase 1 endpoints"""
    
    @patch('pymongo.MongoClient')
    def test_database_connection_test(self, mock_client):
        """Test database connection test endpoint"""
        mock_client.return_value.admin.command.return_value = {"ok": 1}
        mock_client.return_value.__getitem__.return_value.__getitem__.return_value.count_documents.return_value = 50
        
        response = client.get("/api/v1/phase1/connect")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "connected"
        assert "database" in data
        assert "collection" in data
    
    @patch('pymongo.MongoClient')
    def test_database_info(self, mock_client):
        """Test database info endpoint"""
        mock_client.return_value.__getitem__.return_value.command.return_value = {
            "count": 100,
            "size": 1024,
            "avgObjSize": 10,
            "nindexes": 2
        }
        mock_client.return_value.__getitem__.return_value.__getitem__.return_value.find_one.return_value = {
            "field1": "value1",
            "field2": "value2"
        }
        
        response = client.get("/api/v1/phase1/database-info")
        assert response.status_code == 200
        data = response.json()
        assert "database_name" in data
        assert "total_documents" in data
        assert "fields" in data

class TestPhase2Endpoints:
    """Test cases for Phase 2 endpoints"""
    
    def test_generate_scripts(self):
        """Test script generation endpoint"""
        response = client.post(
            "/api/v1/phase2/generate-scripts",
            json={
                "mongo_uri": "mongodb://localhost:27017",
                "source_db": "test_db",
                "source_collection": "raw_statutes"
            }
        )
        assert response.status_code == 200
    
    def test_normalization_status(self):
        """Test normalization status endpoint"""
        response = client.get("/api/v1/phase2/normalization-status")
        assert response.status_code == 200
    
    def test_progress_status(self):
        """Test progress status endpoint"""
        response = client.get("/api/v1/phase2/progress-status")
        assert response.status_code == 200
    
    def test_normalization_history(self):
        """Test normalization history endpoint"""
        response = client.get("/api/v1/phase2/normalization-history?limit=10")
        assert response.status_code == 200

class TestRootEndpoints:
    """Test cases for root endpoints"""
    
    def test_root_endpoint(self):
        """Test root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "LawChronicle API is running!"
        assert data["version"] == "1.0.0"
    
    def test_health_check(self):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

if __name__ == "__main__":
    pytest.main([__file__])
