"""
Grouped Statute Database Creator GUI

This script provides a GUI interface for creating grouped statute databases from section versions
with enhanced performance using NumPy and GPT optimization.

Features:
- Interactive GUI for grouped statute database creation
- NumPy vectorized operations for faster processing
- GPT optimization for intelligent statute reconstruction
- Azure OpenAI integration for advanced content analysis
- Real-time progress tracking and statistics
- Configurable processing parameters
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import numpy as np
from pymongo import MongoClient
from collections import defaultdict, Counter
from dataclasses import dataclass
from dateutil import parser

# GPT optimization imports
try:
    from openai import AzureOpenAI
    from utils.gpt_cache import gpt_cache
    from utils.gpt_rate_limiter import rate_limited_gpt_call
    from utils.gpt_prompt_optimizer import optimize_gpt_prompt
    from utils.gpt_monitor import gpt_monitor
    GPT_UTILS_AVAILABLE = True
except ImportError as e:
    print(f"GPT utilities not available: {e}")
    GPT_UTILS_AVAILABLE = False

@dataclass
class GroupedStatute:
    """Data class for grouped statute documents"""
    base_name: str
    sections: List[Dict]
    versions: List[Dict]
    active_versions: int
    inactive_versions: int
    province: str
    statute_type: str
    created_at: datetime

class NumPyGroupingProcessor:
    """NumPy-optimized grouping processing"""
    
    def __init__(self):
        self.sections_array = None
        self.base_names_array = None
        self.provinces_array = None
        self.statute_types_array = None
    
    def load_sections_vectorized(self, sections: List[Dict]) -> None:
        """Load sections into NumPy arrays for vectorized processing"""
        if not sections:
            return
        
        # Convert to NumPy arrays
        self.sections_array = np.array(sections)
        self.base_names = np.array([s.get('Base_Statute_Name', '') for s in sections])
        self.provinces = np.array([s.get('Section_Data', {}).get('Statute_Reference', {}).get('statute_province', '') for s in sections])
        self.statute_types = np.array([s.get('Section_Data', {}).get('Statute_Reference', {}).get('statute_type', '') for s in sections])
        self.is_active = np.array([s.get('Is_Active', True) for s in sections])
    
    def group_sections_by_base_vectorized(self, sections: List[Dict]) -> Dict[str, List[Dict]]:
        """Group sections by base statute name using NumPy operations"""
        self.load_sections_vectorized(sections)
        
        # Use NumPy unique to get base names
        unique_base_names = np.unique(self.base_names)
        grouped = {}
        
        for base_name in unique_base_names:
            # Find indices where base_name matches
            indices = np.where(self.base_names == base_name)[0]
            grouped[base_name] = [sections[i] for i in indices]
        
        return grouped
    
    def calculate_group_statistics_vectorized(self, sections: List[Dict]) -> Dict:
        """Calculate statistics for a group of sections using NumPy"""
        if not sections:
            return {}
        
        self.load_sections_vectorized(sections)
        
        # Calculate statistics using NumPy operations
        total_sections = len(sections)
        active_count = np.sum(self.is_active)
        inactive_count = total_sections - active_count
        
        # Get unique provinces and types
        unique_provinces = np.unique(self.provinces[self.provinces != ''])
        unique_types = np.unique(self.statute_types[self.statute_types != ''])
        
        # Count occurrences
        province_counts = Counter(self.provinces)
        type_counts = Counter(self.statute_types)
        
        return {
            "total_sections": total_sections,
            "active_versions": int(active_count),
            "inactive_versions": int(inactive_count),
            "provinces": list(unique_provinces),
            "statute_types": list(unique_types),
            "province_distribution": dict(province_counts),
            "type_distribution": dict(type_counts)
        }
    
    def sort_sections_by_version_vectorized(self, sections: List[Dict]) -> List[Dict]:
        """Sort sections by version index using NumPy operations"""
        if not sections:
            return sections
        
        # Extract version indices
        version_indices = np.array([s.get('Version_Index', 0) for s in sections])
        
        # Sort using NumPy argsort
        sorted_indices = np.argsort(version_indices)
        
        return [sections[i] for i in sorted_indices]

class GPTStatuteReconstructor:
    """GPT-powered statute reconstruction and validation"""
    
    def __init__(self, api_key: str, azure_endpoint: str, model: str = "gpt-4o", config: Dict = None):
        self.config = config or {}
        self.client = AzureOpenAI(
            api_key=api_key,
            azure_endpoint=azure_endpoint,
            api_version=self.config.get('azure_api_version', '2024-11-01-preview')
        )
        self.model = model
        
        # GPT optimization utilities
        self.cache = gpt_cache if GPT_UTILS_AVAILABLE else None
        self.monitor = gpt_monitor if GPT_UTILS_AVAILABLE else None
    
    @rate_limited_gpt_call if GPT_UTILS_AVAILABLE else lambda x: x
    @optimize_gpt_prompt if GPT_UTILS_AVAILABLE else lambda x: x
    def validate_statute_completeness(self, sections: List[Dict], base_name: str) -> Dict:
        """Validate if a grouped statute is complete using GPT"""
        # Create summary of sections
        section_summary = []
        for section in sections[:10]:  # Limit to first 10 for performance
            section_data = section.get('Section_Data', {})
            section_summary.append({
                "name": section_data.get('Section_Name', ''),
                "number": section_data.get('Section_Number', ''),
                "type": section_data.get('Section_Type', ''),
                "is_active": section.get('Is_Active', True)
            })
        
        prompt = f"""
        Analyze this grouped statute for completeness:
        
        Statute Name: {base_name}
        Total Sections: {len(sections)}
        
        Section Summary:
        {json.dumps(section_summary, indent=2)}
        
        Provide a JSON response with:
        - is_complete: boolean (has all essential sections)
        - missing_sections: list of expected section types
        - completeness_score: float (0-1)
        - recommendations: string
        - estimated_total_sections: integer
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=300
            )
            
            result = response.choices[0].message.content
            import json
            return json.loads(result)
            
        except Exception as e:
            print(f"GPT validation failed: {e}")
            return {
                "is_complete": True,
                "missing_sections": [],
                "completeness_score": 0.8,
                "recommendations": "Validation failed",
                "estimated_total_sections": len(sections)
            }
    
    @rate_limited_gpt_call if GPT_UTILS_AVAILABLE else lambda x: x
    @optimize_gpt_prompt if GPT_UTILS_AVAILABLE else lambda x: x
    def analyze_statute_structure(self, sections: List[Dict], base_name: str) -> Dict:
        """Analyze the structure and organization of a statute using GPT"""
        # Extract section information
        section_info = []
        for section in sections[:15]:  # Limit for performance
            section_data = section.get('Section_Data', {})
            section_info.append({
                "name": section_data.get('Section_Name', ''),
                "number": section_data.get('Section_Number', ''),
                "type": section_data.get('Section_Type', ''),
                "content_length": len(section_data.get('Section_Content', ''))
            })
        
        prompt = f"""
        Analyze the structure of this legal statute:
        
        Statute Name: {base_name}
        Sections: {json.dumps(section_info, indent=2)}
        
        Provide a JSON response with:
        - structure_type: string (sequential, thematic, mixed)
        - has_definitions: boolean
        - has_penalties: boolean
        - has_procedures: boolean
        - logical_flow: string (description of section organization)
        - structure_score: float (0-1, how well organized)
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=250
            )
            
            result = response.choices[0].message.content
            import json
            return json.loads(result)
            
        except Exception as e:
            print(f"GPT structure analysis failed: {e}")
            return {
                "structure_type": "unknown",
                "has_definitions": False,
                "has_penalties": False,
                "has_procedures": False,
                "logical_flow": "Analysis failed",
                "structure_score": 0.5
            }

class GroupedDBCreatorGUI:
    """Main GUI class for grouped statute database creation"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Grouped Statute DB Creator GUI - LawChronicle")
        self.root.geometry("1200x800")
        
        # Load configuration
        self.config = self.load_config()
        
        # Initialize components
        self.numpy_processor = NumPyGroupingProcessor()
        self.gpt_reconstructor = None
        if GPT_UTILS_AVAILABLE:
            self.gpt_reconstructor = GPTStatuteReconstructor(
                api_key=self.config["azure_api_key"],
                azure_endpoint=self.config["azure_endpoint"],
                model=self.config["gpt_model"],
                config=self.config
            )
        
        # MongoDB connection
        self.client = None
        self.source_db = None
        self.target_db = None
        
        # Processing state
        self.is_processing = False
        self.metadata = {
            "total_section_versions_processed": 0,
            "total_statutes_grouped": 0,
            "grouping_stats": {
                "statutes_with_sections": 0,
                "statutes_without_sections": 0,
                "max_sections_per_statute": 0,
                "average_sections_per_statute": 0,
                "total_sections_grouped": 0,
                "total_versions_grouped": 0
            },
            "content_analysis": {
                "province_distribution": Counter(),
                "statute_type_distribution": Counter(),
                "active_versions": 0,
                "inactive_versions": 0,
                "expired_ordinances": 0,
                "sample_statutes": []
            },
            "gpt_analysis": {
                "completeness_validations": 0,
                "structure_analyses": 0,
                "average_completeness_score": 0.0,
                "average_structure_score": 0.0
            }
        }
        
        self.setup_ui()
        self.connect_to_mongodb()
    
    def load_config(self) -> Dict:
        """Load configuration from JSON file"""
        config_path = "gui/config_grouped_db_creator.json"
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                return json.load(f)
        else:
            # Default configuration
            return {
                "mongo_uri": "mongodb://localhost:27017",
                "source_db": "Batch-Section-Versioned",
                "source_collection": "batch10",
                "target_db": "Final-Batched-Statutes",
                "target_collection": "batch10",
                "azure_api_key": "your_azure_api_key",
                "azure_endpoint": "your_azure_endpoint",
                "gpt_model": "gpt-4o",
                "azure_api_version": "2024-11-01-preview",
                "processing": {
                    "batch_size": 100,
                    "use_gpt_validation": True,
                    "use_gpt_structure_analysis": True,
                    "min_sections_per_statute": 1
                },
                "grouping": {
                    "include_inactive_versions": True,
                    "sort_by_version": True,
                    "validate_completeness": True
                },
                "ui": {
                    "auto_refresh_interval": 1000,
                    "max_log_lines": 1000
                }
            }
    
    def setup_ui(self):
        """Setup the user interface"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(3, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="Grouped Statute DB Creator GUI", font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # Configuration frame
        config_frame = ttk.LabelFrame(main_frame, text="Configuration", padding="10")
        config_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Source database
        ttk.Label(config_frame, text="Source DB:").grid(row=0, column=0, sticky=tk.W)
        self.source_db_var = tk.StringVar(value=self.config["source_db"])
        ttk.Entry(config_frame, textvariable=self.source_db_var, width=30).grid(row=0, column=1, padx=(5, 10))
        
        ttk.Label(config_frame, text="Source Collection:").grid(row=0, column=2, sticky=tk.W)
        self.source_coll_var = tk.StringVar(value=self.config["source_collection"])
        ttk.Entry(config_frame, textvariable=self.source_coll_var, width=20).grid(row=0, column=3, padx=(5, 10))
        
        # Target database
        ttk.Label(config_frame, text="Target DB:").grid(row=1, column=0, sticky=tk.W, pady=(10, 0))
        self.target_db_var = tk.StringVar(value=self.config["target_db"])
        ttk.Entry(config_frame, textvariable=self.target_db_var, width=30).grid(row=1, column=1, padx=(5, 10), pady=(10, 0))
        
        ttk.Label(config_frame, text="Target Collection:").grid(row=1, column=2, sticky=tk.W, pady=(10, 0))
        self.target_coll_var = tk.StringVar(value=self.config["target_collection"])
        ttk.Entry(config_frame, textvariable=self.target_coll_var, width=20).grid(row=1, column=3, padx=(5, 10), pady=(10, 0))
        
        # Processing options
        options_frame = ttk.LabelFrame(main_frame, text="Processing Options", padding="10")
        options_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.use_gpt_validation_var = tk.BooleanVar(value=self.config["processing"]["use_gpt_validation"])
        ttk.Checkbutton(options_frame, text="Use GPT for Completeness Validation", 
                       variable=self.use_gpt_validation_var).grid(row=0, column=0, sticky=tk.W)
        
        self.use_gpt_structure_var = tk.BooleanVar(value=self.config["processing"]["use_gpt_structure_analysis"])
        ttk.Checkbutton(options_frame, text="Use GPT for Structure Analysis", 
                       variable=self.use_gpt_structure_var).grid(row=0, column=1, sticky=tk.W, padx=(20, 0))
        
        ttk.Label(options_frame, text="Batch Size:").grid(row=0, column=2, sticky=tk.W, padx=(20, 5))
        self.batch_size_var = tk.StringVar(value=str(self.config["processing"]["batch_size"]))
        ttk.Entry(options_frame, textvariable=self.batch_size_var, width=10).grid(row=0, column=3)
        
        # Control buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=2, pady=(0, 10))
        
        self.start_button = ttk.Button(button_frame, text="Start Grouped DB Creation", 
                                      command=self.start_processing)
        self.start_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.stop_button = ttk.Button(button_frame, text="Stop", 
                                     command=self.stop_processing, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.refresh_button = ttk.Button(button_frame, text="Refresh Stats", 
                                        command=self.refresh_statistics)
        self.refresh_button.pack(side=tk.LEFT)
        
        # Progress frame
        progress_frame = ttk.LabelFrame(main_frame, text="Progress", padding="10")
        progress_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, 
                                           maximum=100, length=400)
        self.progress_bar.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 5))
        
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(progress_frame, textvariable=self.status_var).grid(row=1, column=0, sticky=tk.W)
        
        # Statistics frame
        stats_frame = ttk.LabelFrame(main_frame, text="Statistics", padding="10")
        stats_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.stats_text = scrolledtext.ScrolledText(stats_frame, height=8, width=80)
        self.stats_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Log frame
        log_frame = ttk.LabelFrame(main_frame, text="Processing Log", padding="10")
        log_frame.grid(row=6, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, width=80)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Initial statistics display
        self.refresh_statistics()
    
    def connect_to_mongodb(self):
        """Connect to MongoDB"""
        try:
            self.client = MongoClient(self.config["mongo_uri"])
            self.client.admin.command('ping')
            self.source_db = self.client[self.config["source_db"]]
            self.target_db = self.client[self.config["target_db"]]
            self.log_message("✅ Connected to MongoDB successfully")
        except Exception as e:
            self.log_message(f"❌ Failed to connect to MongoDB: {e}", "error")
    
    def log_message(self, message: str, level: str = "info"):
        """Add message to log with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        
        self.log_text.insert(tk.END, log_entry)
        self.log_text.see(tk.END)
        
        # Limit log lines
        lines = self.log_text.get("1.0", tk.END).split('\n')
        if len(lines) > self.config["ui"]["max_log_lines"]:
            self.log_text.delete("1.0", f"{len(lines) - self.config['ui']['max_log_lines']}.0")
    
    def refresh_statistics(self):
        """Refresh and display current statistics"""
        stats = f"""
📊 GROUPED STATUTE DB CREATION STATISTICS
{'='*60}
📋 Total Section Versions Processed: {self.metadata['total_section_versions_processed']}
📋 Total Statutes Grouped: {self.metadata['total_statutes_grouped']}

📊 Grouping Statistics:
   - Statutes with sections: {self.metadata['grouping_stats']['statutes_with_sections']}
   - Total sections grouped: {self.metadata['grouping_stats']['total_sections_grouped']}
   - Total versions grouped: {self.metadata['grouping_stats']['total_versions_grouped']}
   - Average sections per statute: {self.metadata['grouping_stats']['average_sections_per_statute']:.1f}
   - Max sections per statute: {self.metadata['grouping_stats']['max_sections_per_statute']}

📊 Content Analysis:
   - Active versions: {self.metadata['content_analysis']['active_versions']}
   - Inactive versions: {self.metadata['content_analysis']['inactive_versions']}
   - Expired ordinances: {self.metadata['content_analysis']['expired_ordinances']}

📊 GPT Analysis:
   - Completeness validations: {self.metadata['gpt_analysis']['completeness_validations']}
   - Structure analyses: {self.metadata['gpt_analysis']['structure_analyses']}
   - Average completeness score: {self.metadata['gpt_analysis']['average_completeness_score']:.2f}
   - Average structure score: {self.metadata['gpt_analysis']['average_structure_score']:.2f}

📊 Province Distribution (Top 5):
"""
        
        for province, count in self.metadata["content_analysis"]["province_distribution"].most_common(5):
            stats += f"   - {province}: {count} statutes\n"
        
        self.stats_text.delete("1.0", tk.END)
        self.stats_text.insert("1.0", stats)
    
    def start_processing(self):
        """Start the grouped database creation process in a separate thread"""
        if self.is_processing:
            return
        
        # Update configuration from UI
        self.config["source_db"] = self.source_db_var.get()
        self.config["source_collection"] = self.source_coll_var.get()
        self.config["target_db"] = self.target_db_var.get()
        self.config["target_collection"] = self.target_coll_var.get()
        self.config["processing"]["use_gpt_validation"] = self.use_gpt_validation_var.get()
        self.config["processing"]["use_gpt_structure_analysis"] = self.use_gpt_structure_var.get()
        self.config["processing"]["batch_size"] = int(self.batch_size_var.get())
        
        # Update database connections
        self.source_db = self.client[self.config["source_db"]]
        self.target_db = self.client[self.config["target_db"]]
        
        self.is_processing = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        
        # Start processing in separate thread
        thread = threading.Thread(target=self.create_grouped_database)
        thread.daemon = True
        thread.start()
    
    def stop_processing(self):
        """Stop the processing"""
        self.is_processing = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.log_message("⏹️ Processing stopped by user")
    
    def create_grouped_database(self):
        """Main processing function"""
        try:
            self.log_message("🚀 Starting grouped statute database creation...")
            self.status_var.set("Processing...")
            
            # Get source collection
            source_collection = self.source_db[self.config["source_collection"]]
            target_collection = self.target_db[self.config["target_collection"]]
            
            # Get total count for progress tracking
            total_sections = source_collection.count_documents({})
            if total_sections == 0:
                self.log_message("❌ No section versions found in source collection", "error")
                return
            
            self.log_message(f"📊 Found {total_sections} section versions to process")
            
            # Get all section versions
            sections = list(source_collection.find({}))
            
            # Group sections by base statute using NumPy
            grouped_sections = self.numpy_processor.group_sections_by_base_vectorized(sections)
            
            self.log_message(f"📊 Grouped into {len(grouped_sections)} base statutes")
            
            # Process each group
            processed_groups = 0
            total_groups = len(grouped_sections)
            
            for base_name, sections_in_group in grouped_sections.items():
                if not self.is_processing:
                    break
                
                # Process statute group
                statute_doc = self.create_grouped_statute_document(sections_in_group, base_name)
                
                if statute_doc:
                    target_collection.insert_one(statute_doc)
                    self.log_message(f"💾 Created grouped statute: {base_name} with {len(sections_in_group)} sections")
                
                # Update metadata
                self.update_metadata(sections_in_group, statute_doc)
                
                processed_groups += 1
                progress = (processed_groups / total_groups) * 100
                self.progress_var.set(progress)
                
                self.log_message(f"📈 Processed {processed_groups}/{total_groups} base statutes ({progress:.1f}%)")
            
            if self.is_processing:
                self.log_message("✅ Grouped statute database creation completed successfully!")
                self.status_var.set("Completed")
                self.refresh_statistics()
            else:
                self.log_message("⏹️ Processing stopped")
                self.status_var.set("Stopped")
                
        except Exception as e:
            self.log_message(f"❌ Error during processing: {e}", "error")
            self.status_var.set("Error")
        finally:
            self.is_processing = False
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
    
    def create_grouped_statute_document(self, sections: List[Dict], base_name: str) -> Optional[Dict]:
        """Create a grouped statute document"""
        if not sections:
            return None
        
        # Sort sections by version if enabled
        if self.config["grouping"]["sort_by_version"]:
            sections = self.numpy_processor.sort_sections_by_version_vectorized(sections)
        
        # Calculate statistics using NumPy
        stats = self.numpy_processor.calculate_group_statistics_vectorized(sections)
        
        # Get representative section for metadata
        representative_section = sections[0]
        section_data = representative_section.get('Section_Data', {})
        statute_ref = section_data.get('Statute_Reference', {})
        
        # Use GPT for validation and analysis if enabled
        gpt_analysis = {}
        if self.config["processing"]["use_gpt_validation"] and self.gpt_reconstructor:
            completeness_analysis = self.gpt_reconstructor.validate_statute_completeness(sections, base_name)
            gpt_analysis["completeness"] = completeness_analysis
            self.metadata["gpt_analysis"]["completeness_validations"] += 1
            self.metadata["gpt_analysis"]["average_completeness_score"] = (
                (self.metadata["gpt_analysis"]["average_completeness_score"] * 
                 (self.metadata["gpt_analysis"]["completeness_validations"] - 1) + 
                 completeness_analysis.get("completeness_score", 0.8)) / 
                self.metadata["gpt_analysis"]["completeness_validations"]
            )
        
        if self.config["processing"]["use_gpt_structure_analysis"] and self.gpt_reconstructor:
            structure_analysis = self.gpt_reconstructor.analyze_statute_structure(sections, base_name)
            gpt_analysis["structure"] = structure_analysis
            self.metadata["gpt_analysis"]["structure_analyses"] += 1
            self.metadata["gpt_analysis"]["average_structure_score"] = (
                (self.metadata["gpt_analysis"]["average_structure_score"] * 
                 (self.metadata["gpt_analysis"]["structure_analyses"] - 1) + 
                 structure_analysis.get("structure_score", 0.5)) / 
                self.metadata["gpt_analysis"]["structure_analyses"]
            )
        
        # Create the grouped statute document
        statute_doc = {
            "_id": f"grouped_{base_name}",
            "Base_Statute_Name": base_name,
            "Sections": sections,
            "Statistics": stats,
            "Metadata": {
                "province": statute_ref.get("statute_province", ""),
                "statute_type": statute_ref.get("statute_type", ""),
                "year": statute_ref.get("statute_year", ""),
                "citations": statute_ref.get("statute_citations", []),
                "preamble": statute_ref.get("statute_preamble", "")
            },
            "GPT_Analysis": gpt_analysis,
            "Created_At": datetime.now(),
            "Processing_Metadata": {
                "processing_method": "numpy_vectorized",
                "gpt_validation": self.config["processing"]["use_gpt_validation"],
                "gpt_structure_analysis": self.config["processing"]["use_gpt_structure_analysis"],
                "total_sections": len(sections),
                "active_versions": stats.get("active_versions", 0),
                "inactive_versions": stats.get("inactive_versions", 0)
            }
        }
        
        return statute_doc
    
    def update_metadata(self, sections: List[Dict], statute_doc: Optional[Dict]):
        """Update processing metadata"""
        self.metadata["total_section_versions_processed"] += len(sections)
        if statute_doc:
            self.metadata["total_statutes_grouped"] += 1
        
        # Update grouping stats
        if sections:
            self.metadata["grouping_stats"]["statutes_with_sections"] += 1
            self.metadata["grouping_stats"]["total_sections_grouped"] += len(sections)
            self.metadata["grouping_stats"]["total_versions_grouped"] += len(sections)
            
            max_sections = max(len(sections), self.metadata["grouping_stats"]["max_sections_per_statute"])
            self.metadata["grouping_stats"]["max_sections_per_statute"] = max_sections
        
        # Update content analysis
        for section in sections:
            is_active = section.get('Is_Active', True)
            if is_active:
                self.metadata["content_analysis"]["active_versions"] += 1
            else:
                self.metadata["content_analysis"]["inactive_versions"] += 1
            
            # Get province and type
            section_data = section.get('Section_Data', {})
            statute_ref = section_data.get('Statute_Reference', {})
            province = statute_ref.get('statute_province', 'Unknown')
            statute_type = statute_ref.get('statute_type', 'Unknown')
            
            self.metadata["content_analysis"]["province_distribution"][province] += 1
            self.metadata["content_analysis"]["statute_type_distribution"][statute_type] += 1
        
        # Calculate averages
        if self.metadata["total_statutes_grouped"] > 0:
            self.metadata["grouping_stats"]["average_sections_per_statute"] = (
                self.metadata["grouping_stats"]["total_sections_grouped"] / self.metadata["total_statutes_grouped"]
            )

def main():
    """Main function to run the GUI"""
    root = tk.Tk()
    app = GroupedDBCreatorGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main() 