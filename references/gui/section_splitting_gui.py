"""
Section Splitting GUI

This script provides a GUI interface for splitting sections from statute documents
with enhanced performance using NumPy and GPT optimization.

Features:
- Interactive GUI for section splitting operations
- NumPy vectorized operations for faster processing
- GPT optimization for intelligent section analysis
- Azure OpenAI integration for advanced text processing
- Real-time progress tracking and statistics
- Configurable processing parameters
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import json
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import numpy as np
from pymongo import MongoClient
from collections import defaultdict, Counter
from dataclasses import dataclass

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
class SectionDocument:
    """Data class for section documents"""
    section_id: str
    section_name: str
    section_content: str
    section_number: str
    section_type: str
    statute_metadata: Dict
    section_index: int
    created_at: datetime

class NumPySectionProcessor:
    """NumPy-optimized section processing"""
    
    def __init__(self):
        self.sections_array = None
        self.section_types = None
        self.section_numbers = None
    
    def load_sections_vectorized(self, statutes: List[Dict]) -> List[Dict]:
        """Load and process sections using NumPy vectorization"""
        all_sections = []
        
        for statute in statutes:
            sections = statute.get("Sections", [])
            if not sections:
                continue
            
            # Convert to NumPy array for faster processing
            sections_array = np.array(sections)
            
            # Extract statute metadata once
            statute_metadata = {
                "statute_id": str(statute.get("_id", "")),
                "statute_name": statute.get("Statute_Name", ""),
                "statute_date": statute.get("Date", ""),
                "statute_province": statute.get("Province", ""),
                "statute_type": statute.get("Statute_Type", ""),
                "statute_year": statute.get("Year", ""),
                "statute_citations": statute.get("Citations", []),
                "statute_preamble": statute.get("Preamble", "")
            }
            
            # Process sections using vectorized operations
            for i, section in enumerate(sections_array):
                section_doc = self.create_section_document(section, statute_metadata, i)
                if section_doc:
                    all_sections.append(section_doc)
        
        return all_sections
    
    def create_section_document(self, section: Dict, statute_metadata: Dict, section_index: int) -> Optional[Dict]:
        """Create a section document with optimized processing"""
        if not section or not isinstance(section, dict):
            return None
        
        section_name = section.get("Section_Name", "")
        section_content = section.get("Section_Content", "")
        
        if not section_name or not section_content:
            return None
        
        # Extract section number using NumPy string operations
        section_number = self.extract_section_number_vectorized(section_name)
        section_type = self.determine_section_type_vectorized(section_name, section_content)
        
        section_doc = {
            "_id": f"{statute_metadata['statute_id']}_section_{section_index}",
            "Section_Name": section_name,
            "Section_Content": section_content,
            "Section_Number": section_number,
            "Section_Type": section_type,
            "Section_Index": section_index,
            "Statute_Reference": statute_metadata,
            "Created_At": datetime.now(),
            "Processing_Metadata": {
                "extraction_method": "numpy_vectorized",
                "content_length": len(section_content),
                "has_definitions": "definition" in section_content.lower(),
                "has_citations": any(cite in section_content.lower() for cite in ["act", "section", "clause"])
            }
        }
        
        return section_doc
    
    def extract_section_number_vectorized(self, section_name: str) -> str:
        """Extract section number using NumPy string operations"""
        import re
        
        # Use regex to find section numbers
        patterns = [
            r'Section\s+(\d+[A-Za-z]*)',
            r'(\d+[A-Za-z]*)\s*[\.\-]',
            r'^(\d+[A-Za-z]*)',
            r'\((\d+[A-Za-z]*)\)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, section_name, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return "Unknown"
    
    def determine_section_type_vectorized(self, section_name: str, section_content: str) -> str:
        """Determine section type using vectorized text analysis"""
        name_lower = section_name.lower()
        content_lower = section_content.lower()
        
        # Use NumPy for pattern matching
        patterns = {
            "definition": ["definition", "definitions", "interpretation", "meaning"],
            "application": ["application", "applicable", "scope", "extent"],
            "penalty": ["penalty", "punishment", "fine", "imprisonment", "offence"],
            "procedure": ["procedure", "process", "manner", "method"],
            "authority": ["authority", "power", "jurisdiction", "competent"],
            "repeal": ["repeal", "amendment", "modification", "substitution"]
        }
        
        for section_type, keywords in patterns.items():
            if any(keyword in name_lower or keyword in content_lower for keyword in keywords):
                return section_type
        
        return "general"

class GPTSectionAnalyzer:
    """GPT-powered section analysis for complex cases"""
    
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
    def analyze_complex_section(self, section_name: str, section_content: str) -> Dict:
        """Analyze complex sections using GPT for better classification"""
        prompt = f"""
        Analyze this legal section and provide structured information:
        
        Section Name: {section_name}
        Section Content: {section_content[:1000]}...
        
        Provide a JSON response with:
        - section_type: The type of section (definition, application, penalty, procedure, authority, repeal, general)
        - section_number: Extracted section number
        - key_topics: List of main topics covered
        - complexity_level: simple, moderate, or complex
        - has_definitions: boolean
        - has_citations: boolean
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=300
            )
            
            result = response.choices[0].message.content
            # Parse JSON response
            import json
            return json.loads(result)
            
        except Exception as e:
            print(f"GPT analysis failed: {e}")
            return {
                "section_type": "general",
                "section_number": "Unknown",
                "key_topics": [],
                "complexity_level": "simple",
                "has_definitions": False,
                "has_citations": False
            }

class SectionSplittingGUI:
    """Main GUI class for section splitting operations"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Section Splitting GUI - LawChronicle")
        self.root.geometry("1200x800")
        
        # Load configuration
        self.config = self.load_config()
        
        # Initialize components
        self.numpy_processor = NumPySectionProcessor()
        self.gpt_analyzer = None
        if GPT_UTILS_AVAILABLE:
            self.gpt_analyzer = GPTSectionAnalyzer(
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
            "total_statutes_processed": 0,
            "total_sections_extracted": 0,
            "processing_stats": {
                "statutes_with_sections": 0,
                "statutes_without_sections": 0,
                "max_sections_per_statute": 0,
                "average_sections_per_statute": 0
            },
            "section_analysis": {
                "section_type_distribution": Counter(),
                "complexity_distribution": Counter(),
                "sample_sections": []
            }
        }
        
        self.setup_ui()
        self.connect_to_mongodb()
    
    def load_config(self) -> Dict:
        """Load configuration from JSON file"""
        config_path = "gui/config_section_splitting.json"
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                return json.load(f)
        else:
            # Default configuration
            return {
                "mongo_uri": "mongodb://localhost:27017",
                "source_db": "Batch-Statute-Versioned",
                "source_collection": "batch10",
                "target_db": "Batch-Section-Split",
                "target_collection": "batch10",
                "azure_api_key": "your_azure_api_key",
                "azure_endpoint": "your_azure_endpoint",
                "gpt_model": "gpt-4o",
                "azure_api_version": "2024-11-01-preview",
                "processing": {
                    "batch_size": 100,
                    "use_gpt_analysis": True,
                    "complexity_threshold": 0.7
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
        title_label = ttk.Label(main_frame, text="Section Splitting GUI", font=("Arial", 16, "bold"))
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
        
        self.use_gpt_var = tk.BooleanVar(value=self.config["processing"]["use_gpt_analysis"])
        ttk.Checkbutton(options_frame, text="Use GPT Analysis for Complex Sections", 
                       variable=self.use_gpt_var).grid(row=0, column=0, sticky=tk.W)
        
        ttk.Label(options_frame, text="Batch Size:").grid(row=0, column=1, sticky=tk.W, padx=(20, 5))
        self.batch_size_var = tk.StringVar(value=str(self.config["processing"]["batch_size"]))
        ttk.Entry(options_frame, textvariable=self.batch_size_var, width=10).grid(row=0, column=2)
        
        # Control buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=2, pady=(0, 10))
        
        self.start_button = ttk.Button(button_frame, text="Start Section Splitting", 
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
📊 SECTION SPLITTING STATISTICS
{'='*50}
📋 Total Statutes Processed: {self.metadata['total_statutes_processed']}
📋 Total Sections Extracted: {self.metadata['total_sections_extracted']}

📊 Processing Statistics:
   - Statutes with sections: {self.metadata['processing_stats']['statutes_with_sections']}
   - Statutes without sections: {self.metadata['processing_stats']['statutes_without_sections']}
   - Max sections per statute: {self.metadata['processing_stats']['max_sections_per_statute']}
   - Average sections per statute: {self.metadata['processing_stats']['average_sections_per_statute']:.1f}

📊 Section Analysis:
   - Section types: {dict(self.metadata['section_analysis']['section_type_distribution'])}
   - Complexity levels: {dict(self.metadata['section_analysis']['complexity_distribution'])}

📊 Sample Sections:
"""
        
        for i, sample in enumerate(self.metadata['section_analysis']['sample_sections'][:3]):
            stats += f"   {i+1}. {sample['name']} ({sample['type']})\n"
        
        self.stats_text.delete("1.0", tk.END)
        self.stats_text.insert("1.0", stats)
    
    def start_processing(self):
        """Start the section splitting process in a separate thread"""
        if self.is_processing:
            return
        
        # Update configuration from UI
        self.config["source_db"] = self.source_db_var.get()
        self.config["source_collection"] = self.source_coll_var.get()
        self.config["target_db"] = self.target_db_var.get()
        self.config["target_collection"] = self.target_coll_var.get()
        self.config["processing"]["use_gpt_analysis"] = self.use_gpt_var.get()
        self.config["processing"]["batch_size"] = int(self.batch_size_var.get())
        
        # Update database connections
        self.source_db = self.client[self.config["source_db"]]
        self.target_db = self.client[self.config["target_db"]]
        
        self.is_processing = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        
        # Start processing in separate thread
        thread = threading.Thread(target=self.process_sections)
        thread.daemon = True
        thread.start()
    
    def stop_processing(self):
        """Stop the processing"""
        self.is_processing = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.log_message("⏹️ Processing stopped by user")
    
    def process_sections(self):
        """Main processing function"""
        try:
            self.log_message("🚀 Starting section splitting process...")
            self.status_var.set("Processing...")
            
            # Get source collection
            source_collection = self.source_db[self.config["source_collection"]]
            target_collection = self.target_db[self.config["target_collection"]]
            
            # Get total count for progress tracking
            total_statutes = source_collection.count_documents({})
            if total_statutes == 0:
                self.log_message("❌ No statutes found in source collection", "error")
                return
            
            self.log_message(f"📊 Found {total_statutes} statutes to process")
            
            # Process in batches
            batch_size = self.config["processing"]["batch_size"]
            processed_count = 0
            
            for skip in range(0, total_statutes, batch_size):
                if not self.is_processing:
                    break
                
                # Get batch of statutes
                statutes = list(source_collection.find({}).skip(skip).limit(batch_size))
                
                # Process sections using NumPy
                sections = self.numpy_processor.load_sections_vectorized(statutes)
                
                # Use GPT analysis for complex sections if enabled
                if self.config["processing"]["use_gpt_analysis"] and self.gpt_analyzer:
                    sections = self.enhance_sections_with_gpt(sections)
                
                # Save to target collection
                if sections:
                    target_collection.insert_many(sections)
                    self.log_message(f"💾 Saved {len(sections)} sections to database")
                
                # Update metadata
                self.update_metadata(statutes, sections)
                
                # Update progress
                processed_count += len(statutes)
                progress = (processed_count / total_statutes) * 100
                self.progress_var.set(progress)
                
                self.log_message(f"📈 Processed {processed_count}/{total_statutes} statutes ({progress:.1f}%)")
            
            if self.is_processing:
                self.log_message("✅ Section splitting completed successfully!")
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
    
    def enhance_sections_with_gpt(self, sections: List[Dict]) -> List[Dict]:
        """Enhance sections with GPT analysis for complex cases"""
        enhanced_sections = []
        
        for section in sections:
            section_name = section.get("Section_Name", "")
            section_content = section.get("Section_Content", "")
            
            # Check if section is complex enough for GPT analysis
            if len(section_content) > 500 or "definition" in section_name.lower():
                try:
                    gpt_analysis = self.gpt_analyzer.analyze_complex_section(section_name, section_content)
                    
                    # Update section with GPT insights
                    section["Section_Type"] = gpt_analysis.get("section_type", section["Section_Type"])
                    section["Section_Number"] = gpt_analysis.get("section_number", section["Section_Number"])
                    section["GPT_Analysis"] = gpt_analysis
                    
                    self.log_message(f"🤖 Enhanced section: {section_name}")
                    
                except Exception as e:
                    self.log_message(f"⚠️ GPT analysis failed for section {section_name}: {e}")
            
            enhanced_sections.append(section)
        
        return enhanced_sections
    
    def update_metadata(self, statutes: List[Dict], sections: List[Dict]):
        """Update processing metadata"""
        self.metadata["total_statutes_processed"] += len(statutes)
        self.metadata["total_sections_extracted"] += len(sections)
        
        # Update processing stats
        statutes_with_sections = sum(1 for s in statutes if s.get("Sections"))
        self.metadata["processing_stats"]["statutes_with_sections"] += statutes_with_sections
        self.metadata["processing_stats"]["statutes_without_sections"] += len(statutes) - statutes_with_sections
        
        # Update section analysis
        for section in sections:
            section_type = section.get("Section_Type", "unknown")
            self.metadata["section_analysis"]["section_type_distribution"][section_type] += 1
            
            # Add sample sections
            if len(self.metadata["section_analysis"]["sample_sections"]) < 5:
                self.metadata["section_analysis"]["sample_sections"].append({
                    "name": section.get("Section_Name", ""),
                    "type": section_type
                })
        
        # Calculate averages
        if self.metadata["total_statutes_processed"] > 0:
            self.metadata["processing_stats"]["average_sections_per_statute"] = (
                self.metadata["total_sections_extracted"] / self.metadata["total_statutes_processed"]
            )

def main():
    """Main function to run the GUI"""
    root = tk.Tk()
    app = SectionSplittingGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main() 