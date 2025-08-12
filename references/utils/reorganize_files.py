#!/usr/bin/env python3
"""
File Reorganization Script for LawChronicle Project

This script reorganizes:
1. JSON metadata files into script-based folders within metadata/
2. Excel files with date patterns into organized_excels/ subfolders
3. Cleans up old phase-based folders
4. Provides detailed logging of all operations

Author: AI Assistant
Date: 2025-01-29
"""

import os
import shutil
import re
import json
from pathlib import Path
from typing import Dict, List, Tuple, Set
from datetime import datetime

class FileReorganizer:
    def __init__(self, project_root: str = None):
        """Initialize the reorganizer with project paths."""
        if project_root is None:
            # Get the project root (two levels up from utils/)
            self.project_root = Path(__file__).parent.parent.absolute()
        else:
            self.project_root = Path(project_root).absolute()
        
        self.metadata_dir = self.project_root / "metadata"
        self.misc_dir = self.metadata_dir / "misc"
        
        # Statistics tracking
        self.stats = {
            "metadata_files_moved": {},
            "excel_files_moved": {},
            "empty_folders_removed": [],
            "skipped_files": [],
            "errors": []
        }
        
        # Date patterns for Excel file detection
        self.date_patterns = [
            r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
            r'\d{2}-\d{2}-\d{4}',  # DD-MM-YYYY
            r'\d{4}_\d{2}',        # YYYY_MM
            r'\d{2}_\d{2}_\d{4}',  # DD_MM_YYYY
            r'\d{4}_\d{2}_\d{2}',  # YYYY_MM_DD
            r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\d{4}',  # jan2024
            r'(january|february|march|april|may|june|july|august|september|october|november|december)\d{4}',  # january2024
            r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)_\d{4}',  # jan_2024
            r'\d{4}(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)',  # 2024jan
        ]
        
        # Script name extraction patterns
        self.script_patterns = [
            r'^(.+?)_metadata',
            r'^(.+?)_summary',
            r'^(.+?)_cleanup',
            r'^(.+?)_versioning',
            r'^(.+?)_grouped',
            r'^(.+?)_section',
            r'^(.+?)_statute',
            r'^(.+?)_batch',
            r'^(.+?)_processing',
            r'^(.+?)_splitting',
            r'^(.+?)_sorting',
            r'^(.+?)_removal',
            r'^(.+?)_enrich',
            r'^(.+?)_parse',
            r'^(.+?)_search',
            r'^(.+?)_normalize',
            r'^(.+?)_export',
            r'^(.+?)_consolidation',
        ]
        
        # Files to exclude from metadata processing
        self.exclude_patterns = [
            r'^config\.json$',
            r'^settings\.json$',
            r'^package\.json$',
            r'^requirements\.json$',
            r'^\.json$',  # Empty or single character names
        ]

    def is_metadata_file(self, filepath: Path) -> bool:
        """Determine if a file should be considered metadata."""
        filename = filepath.name.lower()
        
        # Exclude files that match exclusion patterns
        for pattern in self.exclude_patterns:
            if re.match(pattern, filename, re.IGNORECASE):
                return False
        
        # Must be a JSON file
        if not filename.endswith('.json'):
            return False
        
        # Must contain metadata-related keywords
        metadata_keywords = [
            'metadata', 'summary', 'cleanup', 'versioning', 'grouped', 
            'section', 'sort', 'preamble', 'duplicate', 'normalize', 
            'date', 'export', 'consolidation', 'statute', 'batch',
            'splitting', 'removal', 'enrich', 'parse', 'search'
        ]
        
        return any(keyword in filename for keyword in metadata_keywords)

    def extract_script_name(self, filename: str) -> str:
        """Extract the base script name from a metadata filename."""
        # Remove .json extension
        name_without_ext = filename.replace('.json', '')
        
        # Try to match against script patterns
        for pattern in self.script_patterns:
            match = re.match(pattern, name_without_ext, re.IGNORECASE)
            if match:
                script_name = match.group(1)
                # Clean up the script name
                script_name = re.sub(r'[_-]+', '_', script_name)  # Normalize separators
                script_name = script_name.strip('_')  # Remove leading/trailing underscores
                return script_name
        
        # If no pattern matches, try to extract from common prefixes
        if name_without_ext.startswith('metadata_'):
            return name_without_ext[9:]  # Remove 'metadata_' prefix
        
        # Fallback: return the first part before any underscore
        parts = name_without_ext.split('_')
        if len(parts) > 1:
            return parts[0]
        
        return name_without_ext

    def has_date_pattern(self, filename: str) -> bool:
        """Check if filename contains a date pattern or batch pattern."""
        filename_lower = filename.lower()
        
        # Check for date patterns
        for pattern in self.date_patterns:
            if re.search(pattern, filename_lower):
                return True
        
        # Check for batch patterns (common in this project)
        batch_patterns = [
            r'batch\d+',  # batch1, batch10, etc.
            r'batch_\d+',  # batch_1, batch_10, etc.
            r'batch-\d+',  # batch-1, batch-10, etc.
        ]
        
        for pattern in batch_patterns:
            if re.search(pattern, filename_lower):
                return True
        
        return False

    def find_all_metadata_files(self) -> List[Path]:
        """Recursively find all metadata JSON files in the project."""
        metadata_files = []
        
        for root, dirs, files in os.walk(self.project_root):
            root_path = Path(root)
            
            # Skip the metadata directory itself to avoid processing already organized files
            if root_path == self.metadata_dir:
                continue
            
            for file in files:
                filepath = root_path / file
                if self.is_metadata_file(filepath):
                    metadata_files.append(filepath)
        
        return metadata_files

    def find_all_excel_files(self) -> List[Path]:
        """Recursively find all Excel files in the project."""
        excel_files = []
        
        for root, dirs, files in os.walk(self.project_root):
            root_path = Path(root)
            
            # Skip the metadata directory
            if root_path == self.metadata_dir:
                continue
            
            for file in files:
                if file.lower().endswith(('.xlsx', '.xls')):
                    filepath = root_path / file
                    excel_files.append(filepath)
        
        return excel_files

    def organize_metadata_files(self) -> None:
        """Organize metadata files into script-based folders."""
        print("🔍 Finding metadata files...")
        metadata_files = self.find_all_metadata_files()
        print(f"   Found {len(metadata_files)} metadata files to organize")
        
        for filepath in metadata_files:
            try:
                filename = filepath.name
                script_name = self.extract_script_name(filename)
                
                # Create target directory
                target_dir = self.metadata_dir / script_name
                target_dir.mkdir(parents=True, exist_ok=True)
                
                # Determine target path
                target_path = target_dir / filename
                
                # Handle conflicts
                if target_path.exists() and target_path != filepath:
                    # Generate unique filename
                    base_name = target_path.stem
                    extension = target_path.suffix
                    counter = 1
                    while target_path.exists():
                        new_name = f"{base_name}_{counter}{extension}"
                        target_path = target_dir / new_name
                        counter += 1
                
                # Move the file
                if target_path != filepath:
                    shutil.move(str(filepath), str(target_path))
                    
                    # Update statistics
                    if script_name not in self.stats["metadata_files_moved"]:
                        self.stats["metadata_files_moved"][script_name] = []
                    self.stats["metadata_files_moved"][script_name].append(filename)
                    
                    print(f"   📁 Moved {filename} → metadata/{script_name}/")
                
            except Exception as e:
                error_msg = f"Error processing {filepath}: {str(e)}"
                self.stats["errors"].append(error_msg)
                print(f"   ❌ {error_msg}")

    def organize_excel_files(self) -> None:
        """Organize Excel files with date patterns into organized_excels/ folders."""
        print("🔍 Finding Excel files...")
        excel_files = self.find_all_excel_files()
        print(f"   Found {len(excel_files)} Excel files to check")
        
        for filepath in excel_files:
            try:
                filename = filepath.name
                
                # Check if filename contains date pattern
                if self.has_date_pattern(filename):
                    # Create organized_excels directory in the same folder as the file
                    parent_dir = filepath.parent
                    organized_dir = parent_dir / "organized_excels"
                    organized_dir.mkdir(exist_ok=True)
                    
                    # Determine target path
                    target_path = organized_dir / filename
                    
                    # Handle conflicts
                    if target_path.exists() and target_path != filepath:
                        base_name = target_path.stem
                        extension = target_path.suffix
                        counter = 1
                        while target_path.exists():
                            new_name = f"{base_name}_{counter}{extension}"
                            target_path = organized_dir / new_name
                            counter += 1
                    
                    # Move the file
                    if target_path != filepath:
                        shutil.move(str(filepath), str(target_path))
                        
                        # Update statistics
                        parent_name = str(parent_dir.relative_to(self.project_root))
                        if parent_name not in self.stats["excel_files_moved"]:
                            self.stats["excel_files_moved"][parent_name] = []
                        self.stats["excel_files_moved"][parent_name].append(filename)
                        
                        print(f"   📊 Moved {filename} → {parent_name}/organized_excels/")
                else:
                    self.stats["skipped_files"].append(str(filepath))
                    
            except Exception as e:
                error_msg = f"Error processing {filepath}: {str(e)}"
                self.stats["errors"].append(error_msg)
                print(f"   ❌ {error_msg}")

    def cleanup_empty_folders(self) -> None:
        """Remove empty phase-based folders from metadata/."""
        print("🧹 Cleaning up empty folders...")
        
        # List of old phase folders to check
        old_phase_folders = [
            "ingestion", "normalization", "field_cleaning", 
            "date_processing", "statute_versioning", "section_versioning", 
            "export_pipeline"
        ]
        
        for folder_name in old_phase_folders:
            folder_path = self.metadata_dir / folder_name
            if folder_path.exists() and folder_path.is_dir():
                try:
                    # Check if folder is empty
                    if not any(folder_path.iterdir()):
                        folder_path.rmdir()
                        self.stats["empty_folders_removed"].append(folder_name)
                        print(f"   🗑️  Removed empty folder: metadata/{folder_name}/")
                except Exception as e:
                    error_msg = f"Error removing folder {folder_name}: {str(e)}"
                    self.stats["errors"].append(error_msg)
                    print(f"   ❌ {error_msg}")

    def create_metadata_save_helper(self) -> None:
        """Create a helper module for future metadata saving."""
        helper_content = '''"""
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
'''
        
        helper_path = self.project_root / "utils" / "metadata_helper.py"
        with open(helper_path, 'w', encoding='utf-8') as f:
            f.write(helper_content)
        
        print(f"   📝 Created metadata helper: utils/metadata_helper.py")

    def print_summary(self) -> None:
        """Print a detailed summary of all operations."""
        print("\n" + "="*80)
        print("📊 REORGANIZATION SUMMARY")
        print("="*80)
        
        # Metadata files summary
        print("\n📁 METADATA FILES ORGANIZED:")
        total_metadata_moved = 0
        for script_name, files in self.stats["metadata_files_moved"].items():
            print(f"   {script_name}: {len(files)} files")
            total_metadata_moved += len(files)
        print(f"   Total: {total_metadata_moved} metadata files moved")
        
        # Excel files summary
        print("\n📊 EXCEL FILES ORGANIZED:")
        total_excel_moved = 0
        for folder, files in self.stats["excel_files_moved"].items():
            print(f"   {folder}/organized_excels/: {len(files)} files")
            total_excel_moved += len(files)
        print(f"   Total: {total_excel_moved} Excel files moved")
        
        # Empty folders removed
        if self.stats["empty_folders_removed"]:
            print(f"\n🗑️  EMPTY FOLDERS REMOVED:")
            for folder in self.stats["empty_folders_removed"]:
                print(f"   metadata/{folder}/")
        
        # Skipped files
        if self.stats["skipped_files"]:
            print(f"\n⏭️  SKIPPED FILES ({len(self.stats['skipped_files'])}):")
            for file in self.stats["skipped_files"][:10]:  # Show first 10
                print(f"   {file}")
            if len(self.stats["skipped_files"]) > 10:
                print(f"   ... and {len(self.stats['skipped_files']) - 10} more")
        
        # Errors
        if self.stats["errors"]:
            print(f"\n❌ ERRORS ({len(self.stats['errors'])}):")
            for error in self.stats["errors"]:
                print(f"   {error}")
        
        print("\n" + "="*80)
        print("✅ Reorganization complete!")
        print("="*80)

    def run(self) -> None:
        """Execute the complete reorganization process."""
        print("🚀 Starting file reorganization...")
        print(f"📂 Project root: {self.project_root}")
        print(f"📁 Metadata directory: {self.metadata_dir}")
        
        # Ensure metadata directory exists
        self.metadata_dir.mkdir(exist_ok=True)
        
        # Step 1: Organize metadata files
        print("\n1️⃣  Organizing metadata files...")
        self.organize_metadata_files()
        
        # Step 2: Organize Excel files
        print("\n2️⃣  Organizing Excel files...")
        self.organize_excel_files()
        
        # Step 3: Clean up empty folders
        print("\n3️⃣  Cleaning up empty folders...")
        self.cleanup_empty_folders()
        
        # Step 4: Create metadata helper
        print("\n4️⃣  Creating metadata helper...")
        self.create_metadata_save_helper()
        
        # Step 5: Print summary
        self.print_summary()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Reorganize metadata and Excel files in the LawChronicle project"
    )
    parser.add_argument(
        "--project-root", 
        type=str, 
        help="Path to project root (default: auto-detect)"
    )
    parser.add_argument(
        "--dry-run", 
        action="store_true", 
        help="Show what would be done without actually moving files"
    )
    
    args = parser.parse_args()
    
    # Create reorganizer
    reorganizer = FileReorganizer(args.project_root)
    
    if args.dry_run:
        print("🔍 DRY RUN MODE - No files will be moved")
        # TODO: Implement dry run functionality
        print("Dry run mode not yet implemented. Use without --dry-run to execute.")
    else:
        # Run the reorganization
        reorganizer.run()


if __name__ == "__main__":
    main() 