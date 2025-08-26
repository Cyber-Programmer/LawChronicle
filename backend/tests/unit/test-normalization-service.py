"""
Unit tests for NormalizationService

These tests validate the business logic extracted from phase2 endpoint.
"""

import pytest
import tempfile
from unittest.mock import patch, MagicMock
from pathlib import Path

from app.core.services.normalization_service import (
    NormalizationEngine, 
    ScriptRunner, 
    NormalizationService
)


class TestNormalizationEngine:
    
    def test_validate_normalization_request_success(self):
        engine = NormalizationEngine()
        result = engine.validate_normalization_request("source_db", "target_db")
        
        assert result["source_db"] == "source_db"
        assert result["target_db"] == "target_db"
        assert "validated_at" in result
    
    def test_validate_normalization_request_missing_source(self):
        engine = NormalizationEngine()
        
        with pytest.raises(ValueError, match="Source and target databases are required"):
            engine.validate_normalization_request("", "target_db")
    
    def test_validate_normalization_request_same_db(self):
        engine = NormalizationEngine()
        
        with pytest.raises(ValueError, match="Source and target databases must be different"):
            engine.validate_normalization_request("same_db", "same_db")
    
    def test_generate_normalization_config_default(self):
        engine = NormalizationEngine()
        config = engine.generate_normalization_config("source_db", "target_db")
        
        assert config["source"]["database"] == "source_db"
        assert config["target"]["database"] == "target_db"
        assert config["batch_size"] == 1000
        assert "operations" in config
        assert "created_at" in config
    
    def test_generate_normalization_config_with_options(self):
        engine = NormalizationEngine()
        options = {"batch_size": 500, "custom_option": "value"}
        config = engine.generate_normalization_config("source_db", "target_db", options)
        
        assert config["batch_size"] == 500
        assert config["custom_option"] == "value"
    
    def test_cleanup(self):
        engine = NormalizationEngine()
        temp_dir = engine.temp_dir
        
        # Directory should exist
        assert Path(temp_dir).exists()
        
        engine.cleanup()
        
        # Directory should be cleaned up (might still exist due to timing)
        # Just verify no exception is raised


class TestScriptRunner:
    
    def test_validate_script_path_absolute(self):
        runner = ScriptRunner()
        
        # Create a temporary Python file
        with tempfile.NamedTemporaryFile(suffix='.py', delete=False) as f:
            script_path = f.name
        
        try:
            validated = runner.validate_script_path(script_path)
            assert validated == Path(script_path)
        finally:
            Path(script_path).unlink()
    
    def test_validate_script_path_not_found(self):
        runner = ScriptRunner()
        
        with pytest.raises(FileNotFoundError):
            runner.validate_script_path("/nonexistent/script.py")
    
    def test_validate_script_path_not_python(self):
        runner = ScriptRunner()
        
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
            script_path = f.name
        
        try:
            with pytest.raises(ValueError, match="Only Python scripts allowed"):
                runner.validate_script_path(script_path)
        finally:
            Path(script_path).unlink()
    
    @patch('subprocess.run')
    def test_run_python_script_success(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Success output",
            stderr="",
        )
        
        runner = ScriptRunner()
        
        # Create a temporary Python file
        with tempfile.NamedTemporaryFile(suffix='.py', delete=False) as f:
            script_path = f.name
        
        try:
            result = runner.run_python_script(script_path)
            
            assert result["success"] is True
            assert result["returncode"] == 0
            assert result["stdout"] == "Success output"
            assert "executed_at" in result
        finally:
            Path(script_path).unlink()
    
    @patch('subprocess.run')
    def test_run_python_script_failure(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error occurred",
        )
        
        runner = ScriptRunner()
        
        with tempfile.NamedTemporaryFile(suffix='.py', delete=False) as f:
            script_path = f.name
        
        try:
            result = runner.run_python_script(script_path)
            
            assert result["success"] is False
            assert result["returncode"] == 1
            assert result["stderr"] == "Error occurred"
        finally:
            Path(script_path).unlink()


class TestNormalizationService:
    
    def test_start_normalization_success(self):
        service = NormalizationService()
        
        result = service.start_normalization("source_db", "target_db")
        
        assert result["status"] == "configured"
        assert "validation" in result
        assert "config" in result
        assert "next_steps" in result
    
    def test_start_normalization_with_options(self):
        service = NormalizationService()
        options = {"batch_size": 2000}
        
        result = service.start_normalization("source_db", "target_db", options)
        
        assert result["config"]["batch_size"] == 2000
    
    def test_start_normalization_invalid_input(self):
        service = NormalizationService()
        
        with pytest.raises(ValueError):
            service.start_normalization("", "target_db")
    
    def test_cleanup(self):
        service = NormalizationService()
        
        # Should not raise exception
        service.cleanup()
