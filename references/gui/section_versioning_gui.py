"""
Section Versioning GUI

This script provides a GUI interface for assigning section versions with semantic similarity
and enhanced performance using NumPy and GPT optimization.

Features:
- Interactive GUI for section versioning operations
- NumPy vectorized operations for faster processing
- GPT optimization for semantic similarity analysis
- Azure OpenAI integration for intelligent version ordering
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
import difflib
import re

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

# Fuzzy matching imports
try:
    from fuzzywuzzy import fuzz
except ImportError:
    def fuzz_ratio(s1, s2):
        return difflib.SequenceMatcher(None, s1, s2).ratio() * 100
    
    def fuzz_partial_ratio(s1, s2):
        return difflib.SequenceMatcher(None, s1, s2).ratio() * 100
    
    class Fuzz:
        @staticmethod
        def ratio(s1, s2):
            return fuzz_ratio(s1, s2)
        
        @staticmethod
        def partial_ratio(s1, s2):
            return fuzz_partial_ratio(s1, s2)
    
    fuzz = Fuzz()

@dataclass
class SectionVersion:
    """Data class for section versions"""
    section_id: str
    section_name: str
    section_content: str
    section_number: str
    version_label: str
    is_active: bool
    promulgation_date: Optional[datetime]
    statute_metadata: Dict
    similarity_score: float

class NumPyVersionProcessor:
    """NumPy-optimized version processing"""
    
    def __init__(self):
        self.sections_array = None
        self.similarity_matrix = None
        self.date_array = None
    
    def load_sections_vectorized(self, sections: List[Dict]) -> None:
        """Load sections into NumPy arrays for vectorized processing"""
        if not sections:
            return
        
        # Convert to NumPy arrays
        self.sections_array = np.array(sections)
        self.section_names = np.array([s.get('Section_Name', '') for s in sections])
        self.section_contents = np.array([s.get('Section_Content', '') for s in sections])
        self.section_numbers = np.array([s.get('Section_Number', '') for s in sections])
        
        # Parse dates vectorized
        self.date_array = np.vectorize(self.parse_date_safe)([s.get('Date', '') for s in sections])
    
    def parse_date_safe(self, date_str: str) -> Optional[datetime]:
        """Safely parse date string"""
        if not date_str:
            return None
        try:
            return parser.parse(date_str)
        except:
            return None
    
    def calculate_similarity_matrix(self) -> np.ndarray:
        """Calculate similarity matrix using NumPy operations"""
        n = len(self.sections_array)
        similarity_matrix = np.zeros((n, n))
        
        for i in range(n):
            for j in range(i+1, n):
                similarity = self.calculate_section_similarity(
                    self.sections_array[i], 
                    self.sections_array[j]
                )
                similarity_matrix[i][j] = similarity
                similarity_matrix[j][i] = similarity
        
        return similarity_matrix
    
    def calculate_section_similarity(self, section_a: Dict, section_b: Dict) -> float:
        """Calculate similarity between two sections"""
        name_a = section_a.get('Section_Name', '')
        name_b = section_b.get('Section_Name', '')
        content_a = section_a.get('Section_Content', '')
        content_b = section_b.get('Section_Content', '')
        
        # Name similarity
        name_similarity = fuzz.ratio(name_a.lower(), name_b.lower()) / 100.0
        
        # Content similarity (use first 500 chars for performance)
        content_a_short = content_a[:500]
        content_b_short = content_b[:500]
        content_similarity = fuzz.partial_ratio(content_a_short.lower(), content_b_short.lower()) / 100.0
        
        # Weighted average
        return 0.4 * name_similarity + 0.6 * content_similarity
    
    def group_similar_sections_vectorized(self, sections: List[Dict], threshold: float = 0.85) -> List[List[Dict]]:
        """Group similar sections using NumPy operations"""
        self.load_sections_vectorized(sections)
        similarity_matrix = self.calculate_similarity_matrix()
        
        # Find groups using connected components
        groups = []
        visited = set()
        
        for i in range(len(sections)):
            if i in visited:
                continue
            
            # Start new group
            group = [sections[i]]
            visited.add(i)
            
            # Find similar sections
            for j in range(i+1, len(sections)):
                if j not in visited and similarity_matrix[i][j] >= threshold:
                    group.append(sections[j])
                    visited.add(j)
            
            if len(group) > 1:  # Only keep groups with multiple sections
                groups.append(group)
        
        return groups
    
    def sort_sections_by_date_vectorized(self, sections: List[Dict]) -> List[Dict]:
        """Sort sections by date using NumPy operations"""
        if not sections:
            return sections
        
        # Extract dates
        dates = []
        for section in sections:
            date_str = section.get('Date', '')
            parsed_date = self.parse_date_safe(date_str)
            dates.append(parsed_date if parsed_date else datetime.min)
        
        # Sort using NumPy argsort
        date_array = np.array(dates)
        sorted_indices = np.argsort(date_array)
        
        return [sections[i] for i in sorted_indices]

class GPTSectionDisambiguator:
    """GPT-powered section disambiguation and version ordering"""
    
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
    def check_section_equivalence(self, section_a: Dict, section_b: Dict) -> Dict:
        """Check if two sections are equivalent using GPT"""
        prompt = f"""
        Analyze these two legal sections and determine if they are the same section from different versions:
        
        Section A:
        Name: {section_a.get('Section_Name', '')}
        Content: {section_a.get('Section_Content', '')[:500]}...
        Date: {section_a.get('Date', '')}
        
        Section B:
        Name: {section_b.get('Section_Name', '')}
        Content: {section_b.get('Section_Content', '')[:500]}...
        Date: {section_b.get('Date', '')}
        
        Provide a JSON response with:
        - are_equivalent: boolean
        - confidence: float (0-1)
        - reasoning: string
        - version_order: "A_first", "B_first", or "same_date"
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=200
            )
            
            result = response.choices[0].message.content
            import json
            return json.loads(result)
            
        except Exception as e:
            print(f"GPT analysis failed: {e}")
            return {
                "are_equivalent": False,
                "confidence": 0.0,
                "reasoning": "Analysis failed",
                "version_order": "same_date"
            }
    
    @rate_limited_gpt_call if GPT_UTILS_AVAILABLE else lambda x: x
    @optimize_gpt_prompt if GPT_UTILS_AVAILABLE else lambda x: x
    def determine_version_order(self, section_a: Dict, section_b: Dict, group_name: str = "") -> Dict:
        """Determine the chronological order of two section versions"""
        prompt = f"""
        Determine the chronological order of these two legal section versions:
        
        Section A:
        Name: {section_a.get('Section_Name', '')}
        Date: {section_a.get('Date', '')}
        Content: {section_a.get('Section_Content', '')[:300]}...
        
        Section B:
        Name: {section_b.get('Section_Name', '')}
        Date: {section_b.get('Date', '')}
        Content: {section_b.get('Section_Content', '')[:300]}...
        
        Group: {group_name}
        
        Provide a JSON response with:
        - order: "A_first", "B_first", or "uncertain"
        - confidence: float (0-1)
        - reasoning: string
        - is_ordinance_expired: boolean (if either is an ordinance older than 6 months)
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=200
            )
            
            result = response.choices[0].message.content
            import json
            return json.loads(result)
            
        except Exception as e:
            print(f"GPT version ordering failed: {e}")
            return {
                "order": "uncertain",
                "confidence": 0.0,
                "reasoning": "Analysis failed",
                "is_ordinance_expired": False
            }

class SectionVersioningGUI:
    """Main GUI class for section versioning operations"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Section Versioning GUI - LawChronicle")
        self.root.geometry("1200x800")
        
        # Load configuration
        self.config = self.load_config()
        
        # Initialize components
        self.numpy_processor = NumPyVersionProcessor()
        self.gpt_disambiguator = None
        if GPT_UTILS_AVAILABLE:
            self.gpt_disambiguator = GPTSectionDisambiguator(
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
            "total_sections_processed": 0,
            "total_section_versions_created": 0,
            "versioning_stats": {
                "base_statutes_processed": 0,
                "section_numbers_processed": 0,
                "groups_with_single_version": 0,
                "groups_with_multiple_versions": 0,
                "max_versions_in_group": 0,
                "average_versions_per_group": 0
            },
            "similarity_analysis": {
                "high_similarity_groups": 0,
                "medium_similarity_groups": 0,
                "low_similarity_groups": 0,
                "gpt_disambiguation_count": 0
            }
        }
        
        self.setup_ui()
        self.connect_to_mongodb()
    
    def load_config(self) -> Dict:
        """Load configuration from JSON file"""
        config_path = "gui/config_section_versioning.json"
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                return json.load(f)
        else:
            # Default configuration
            return {
                "mongo_uri": "mongodb://localhost:27017",
                "source_db": "Batch-Section-Split",
                "source_collection": "batch10",
                "target_db": "Batch-Section-Versioned",
                "target_collection": "batch10",
                "azure_api_key": "your_azure_api_key",
                "azure_endpoint": "your_azure_endpoint",
                "gpt_model": "gpt-4o",
                "azure_api_version": "2024-11-01-preview",
                "processing": {
                    "similarity_threshold": 0.85,
                    "text_similarity_threshold": 0.80,
                    "use_gpt_disambiguation": True,
                    "batch_size": 100
                },
                "versioning": {
                    "ordinance_expiration_months": 6,
                    "default_version_label": "v1",
                    "version_naming": "sequential"
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
        title_label = ttk.Label(main_frame, text="Section Versioning GUI", font=("Arial", 16, "bold"))
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
        
        self.use_gpt_var = tk.BooleanVar(value=self.config["processing"]["use_gpt_disambiguation"])
        ttk.Checkbutton(options_frame, text="Use GPT for Disambiguation", 
                       variable=self.use_gpt_var).grid(row=0, column=0, sticky=tk.W)
        
        ttk.Label(options_frame, text="Similarity Threshold:").grid(row=0, column=1, sticky=tk.W, padx=(20, 5))
        self.similarity_threshold_var = tk.StringVar(value=str(self.config["processing"]["similarity_threshold"]))
        ttk.Entry(options_frame, textvariable=self.similarity_threshold_var, width=10).grid(row=0, column=2)
        
        ttk.Label(options_frame, text="Batch Size:").grid(row=0, column=3, sticky=tk.W, padx=(20, 5))
        self.batch_size_var = tk.StringVar(value=str(self.config["processing"]["batch_size"]))
        ttk.Entry(options_frame, textvariable=self.batch_size_var, width=10).grid(row=0, column=4)
        
        # Control buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=2, pady=(0, 10))
        
        self.start_button = ttk.Button(button_frame, text="Start Section Versioning", 
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
📊 SECTION VERSIONING STATISTICS
{'='*50}
📋 Total Sections Processed: {self.metadata['total_sections_processed']}
📋 Total Section Versions Created: {self.metadata['total_section_versions_created']}

📊 Versioning Statistics:
   - Base statutes processed: {self.metadata['versioning_stats']['base_statutes_processed']}
   - Section numbers processed: {self.metadata['versioning_stats']['section_numbers_processed']}
   - Groups with single version: {self.metadata['versioning_stats']['groups_with_single_version']}
   - Groups with multiple versions: {self.metadata['versioning_stats']['groups_with_multiple_versions']}
   - Max versions in group: {self.metadata['versioning_stats']['max_versions_in_group']}
   - Average versions per group: {self.metadata['versioning_stats']['average_versions_per_group']:.1f}

📊 Similarity Analysis:
   - High similarity groups: {self.metadata['similarity_analysis']['high_similarity_groups']}
   - Medium similarity groups: {self.metadata['similarity_analysis']['medium_similarity_groups']}
   - Low similarity groups: {self.metadata['similarity_analysis']['low_similarity_groups']}
   - GPT disambiguation count: {self.metadata['similarity_analysis']['gpt_disambiguation_count']}
"""
        
        self.stats_text.delete("1.0", tk.END)
        self.stats_text.insert("1.0", stats)
    
    def start_processing(self):
        """Start the section versioning process in a separate thread"""
        if self.is_processing:
            return
        
        # Update configuration from UI
        self.config["source_db"] = self.source_db_var.get()
        self.config["source_collection"] = self.source_coll_var.get()
        self.config["target_db"] = self.target_db_var.get()
        self.config["target_collection"] = self.target_coll_var.get()
        self.config["processing"]["use_gpt_disambiguation"] = self.use_gpt_var.get()
        self.config["processing"]["similarity_threshold"] = float(self.similarity_threshold_var.get())
        self.config["processing"]["batch_size"] = int(self.batch_size_var.get())
        
        # Update database connections
        self.source_db = self.client[self.config["source_db"]]
        self.target_db = self.client[self.config["target_db"]]
        
        self.is_processing = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        
        # Start processing in separate thread
        thread = threading.Thread(target=self.process_section_versions)
        thread.daemon = True
        thread.start()
    
    def stop_processing(self):
        """Stop the processing"""
        self.is_processing = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.log_message("⏹️ Processing stopped by user")
    
    def process_section_versions(self):
        """Main processing function"""
        try:
            self.log_message("🚀 Starting section versioning process...")
            self.status_var.set("Processing...")
            
            # Get source collection
            source_collection = self.source_db[self.config["source_collection"]]
            target_collection = self.target_db[self.config["target_collection"]]
            
            # Get total count for progress tracking
            total_sections = source_collection.count_documents({})
            if total_sections == 0:
                self.log_message("❌ No sections found in source collection", "error")
                return
            
            self.log_message(f"📊 Found {total_sections} sections to process")
            
            # Group sections by base statute and section number
            sections = list(source_collection.find({}))
            grouped_sections = self.group_sections_by_base_and_number(sections)
            
            self.log_message(f"📊 Grouped into {len(grouped_sections)} base groups")
            
            # Process each group
            processed_groups = 0
            total_groups = len(grouped_sections)
            
            for base_name, section_groups in grouped_sections.items():
                if not self.is_processing:
                    break
                
                for section_number, sections_in_group in section_groups.items():
                    if not self.is_processing:
                        break
                    
                    # Process section group
                    version_docs = self.process_section_group(sections_in_group, base_name, section_number)
                    
                    if version_docs:
                        target_collection.insert_many(version_docs)
                        self.log_message(f"💾 Created {len(version_docs)} versions for {base_name} - {section_number}")
                    
                    # Update metadata
                    self.update_metadata(sections_in_group, version_docs)
                
                processed_groups += 1
                progress = (processed_groups / total_groups) * 100
                self.progress_var.set(progress)
                
                self.log_message(f"📈 Processed {processed_groups}/{total_groups} base groups ({progress:.1f}%)")
            
            if self.is_processing:
                self.log_message("✅ Section versioning completed successfully!")
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
    
    def group_sections_by_base_and_number(self, sections: List[Dict]) -> Dict[str, Dict[str, List[Dict]]]:
        """Group sections by base statute name and section number"""
        grouped = defaultdict(lambda: defaultdict(list))
        
        for section in sections:
            statute_ref = section.get("Statute_Reference", {})
            base_name = statute_ref.get("statute_name", "Unknown")
            section_number = section.get("Section_Number", "Unknown")
            
            grouped[base_name][section_number].append(section)
        
        return grouped
    
    def process_section_group(self, sections: List[Dict], base_name: str, section_number: str) -> List[Dict]:
        """Process a group of similar sections to create versions"""
        if len(sections) == 1:
            # Single section - create version with default label
            section = sections[0]
            version_doc = self.create_section_version_document(
                base_name, section_number, [section]
            )
            return [version_doc] if version_doc else []
        
        # Multiple sections - find similar groups
        similarity_threshold = self.config["processing"]["similarity_threshold"]
        similar_groups = self.numpy_processor.group_similar_sections_vectorized(
            sections, similarity_threshold
        )
        
        version_docs = []
        
        for group in similar_groups:
            if len(group) == 1:
                # Single section in group
                version_doc = self.create_section_version_document(
                    base_name, section_number, group
                )
                if version_doc:
                    version_docs.append(version_doc)
            else:
                # Multiple similar sections - create versions
                version_docs.extend(self.create_versions_from_group(group, base_name, section_number))
        
        return version_docs
    
    def create_versions_from_group(self, sections: List[Dict], base_name: str, section_number: str) -> List[Dict]:
        """Create version documents from a group of similar sections"""
        # Sort sections by date
        sorted_sections = self.numpy_processor.sort_sections_by_date_vectorized(sections)
        
        # Use GPT for disambiguation if enabled
        if self.config["processing"]["use_gpt_disambiguation"] and self.gpt_disambiguator:
            sorted_sections = self.disambiguate_with_gpt(sorted_sections, base_name, section_number)
        
        # Create version documents
        version_docs = []
        for i, section in enumerate(sorted_sections):
            version_label = f"v{i+1}"
            
            # Check if ordinance is expired
            is_active = self.check_ordinance_expiration(section)
            
            version_doc = {
                "_id": f"{base_name}_{section_number}_{version_label}",
                "Base_Statute_Name": base_name,
                "Section_Number": section_number,
                "Version_Label": version_label,
                "Section_Data": section,
                "Is_Active": is_active,
                "Version_Index": i,
                "Total_Versions": len(sorted_sections),
                "Created_At": datetime.now(),
                "Processing_Metadata": {
                    "processing_method": "numpy_vectorized",
                    "gpt_disambiguation": self.config["processing"]["use_gpt_disambiguation"],
                    "similarity_threshold": self.config["processing"]["similarity_threshold"]
                }
            }
            
            version_docs.append(version_doc)
        
        return version_docs
    
    def disambiguate_with_gpt(self, sections: List[Dict], base_name: str, section_number: str) -> List[Dict]:
        """Use GPT to disambiguate and order section versions"""
        if len(sections) < 2:
            return sections
        
        self.log_message(f"🤖 Using GPT disambiguation for {base_name} - {section_number}")
        self.metadata["similarity_analysis"]["gpt_disambiguation_count"] += 1
        
        # Compare sections pairwise
        for i in range(len(sections) - 1):
            for j in range(i + 1, len(sections)):
                try:
                    gpt_result = self.gpt_disambiguator.determine_version_order(
                        sections[i], sections[j], f"{base_name} - {section_number}"
                    )
                    
                    # Reorder based on GPT result
                    if gpt_result["order"] == "B_first":
                        sections[i], sections[j] = sections[j], sections[i]
                    
                except Exception as e:
                    self.log_message(f"⚠️ GPT disambiguation failed: {e}")
        
        return sections
    
    def check_ordinance_expiration(self, section: Dict) -> bool:
        """Check if ordinance is expired (6+ months old)"""
        date_str = section.get("Date", "")
        if not date_str:
            return True  # Assume active if no date
        
        try:
            promulgation_date = parser.parse(date_str)
            expiration_date = promulgation_date + timedelta(days=180)  # 6 months
            return datetime.now() < expiration_date
        except:
            return True  # Assume active if date parsing fails
    
    def create_section_version_document(self, base_name: str, section_number: str, 
                                      sections: List[Dict]) -> Optional[Dict]:
        """Create a section version document"""
        if not sections:
            return None
        
        section = sections[0]  # Use first section for single version
        is_active = self.check_ordinance_expiration(section)
        
        return {
            "_id": f"{base_name}_{section_number}_v1",
            "Base_Statute_Name": base_name,
            "Section_Number": section_number,
            "Version_Label": "v1",
            "Section_Data": section,
            "Is_Active": is_active,
            "Version_Index": 0,
            "Total_Versions": 1,
            "Created_At": datetime.now(),
            "Processing_Metadata": {
                "processing_method": "numpy_vectorized",
                "gpt_disambiguation": False,
                "similarity_threshold": self.config["processing"]["similarity_threshold"]
            }
        }
    
    def update_metadata(self, sections: List[Dict], version_docs: List[Dict]):
        """Update processing metadata"""
        self.metadata["total_sections_processed"] += len(sections)
        self.metadata["total_section_versions_created"] += len(version_docs)
        
        # Update versioning stats
        if version_docs:
            max_versions = max(len(version_docs), self.metadata["versioning_stats"]["max_versions_in_group"])
            self.metadata["versioning_stats"]["max_versions_in_group"] = max_versions
            
            if len(version_docs) == 1:
                self.metadata["versioning_stats"]["groups_with_single_version"] += 1
            else:
                self.metadata["versioning_stats"]["groups_with_multiple_versions"] += 1
        
        # Update similarity analysis
        if len(sections) > 1:
            avg_similarity = sum(
                self.numpy_processor.calculate_section_similarity(sections[i], sections[j])
                for i in range(len(sections))
                for j in range(i+1, len(sections))
            ) / (len(sections) * (len(sections) - 1) / 2)
            
            if avg_similarity >= 0.9:
                self.metadata["similarity_analysis"]["high_similarity_groups"] += 1
            elif avg_similarity >= 0.7:
                self.metadata["similarity_analysis"]["medium_similarity_groups"] += 1
            else:
                self.metadata["similarity_analysis"]["low_similarity_groups"] += 1

def main():
    """Main function to run the GUI"""
    root = tk.Tk()
    app = SectionVersioningGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main() 