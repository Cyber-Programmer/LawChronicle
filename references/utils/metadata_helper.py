"""
Metadata Save Helper for LawChronicle Project

This module provides utilities for automatically saving metadata files
in the correct script-based folders within the metadata/ directory.

Usage:
    from utils.metadata_helper import save_metadata
    
    # Save metadata for current script
    save_metadata("my_data", "my_script_name")
    
    # Or let it auto-detect script name
    save_metadata("my_data")
"""

import os
import json
from pathlib import Path
from datetime import datetime
import inspect

def get_script_name() -> str:
    """Get the name of the calling script."""
    # Get the frame of the calling function
    frame = inspect.currentframe()
    try:
        # Go up the call stack to find the script that called this function
        while frame:
            frame = frame.f_back
            if frame and frame.f_code.co_filename != __file__:
                script_path = frame.f_code.co_filename
                script_name = Path(script_path).stem
                return script_name
    finally:
        # Clean up the frame reference
        del frame
    
    return "unknown_script"

def save_metadata(data: dict, script_name: str = None, filename_suffix: str = None) -> str:
    """
    Save metadata to the appropriate script folder.
    
    Args:
        data: Dictionary containing metadata to save
        script_name: Name of the script (auto-detected if None)
        filename_suffix: Optional suffix for the filename
    
    Returns:
        Path to the saved file
    """
    if script_name is None:
        script_name = get_script_name()
    
    # Get project root and metadata directory
    project_root = Path(__file__).parent.parent.absolute()
    metadata_dir = project_root / "metadata"
    
    # Create script-specific directory
    script_dir = metadata_dir / script_name
    script_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate filename
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    if filename_suffix:
        filename = f"{script_name}_{filename_suffix}_{timestamp}.json"
    else:
        filename = f"{script_name}_metadata_{timestamp}.json"
    
    # Save the file
    filepath = script_dir / filename
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"📁 Metadata saved: {filepath}")
    return str(filepath)

def save_metadata_with_custom_name(data: dict, filename: str, script_name: str = None) -> str:
    """
    Save metadata with a custom filename.
    
    Args:
        data: Dictionary containing metadata to save
        filename: Custom filename (without .json extension)
        script_name: Name of the script (auto-detected if None)
    
    Returns:
        Path to the saved file
    """
    if script_name is None:
        script_name = get_script_name()
    
    # Ensure filename has .json extension
    if not filename.endswith('.json'):
        filename += '.json'
    
    # Get project root and metadata directory
    project_root = Path(__file__).parent.parent.absolute()
    metadata_dir = project_root / "metadata"
    
    # Create script-specific directory
    script_dir = metadata_dir / script_name
    script_dir.mkdir(parents=True, exist_ok=True)
    
    # Save the file
    filepath = script_dir / filename
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"📁 Metadata saved: {filepath}")
    return str(filepath)
