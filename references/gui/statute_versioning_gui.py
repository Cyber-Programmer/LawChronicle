"""
Statute Versioning GUI Application

A comprehensive GUI for assigning version labels to statutes within each base group.
Provides user control over all aspects of the versioning process with real-time feedback.

Features:
- Interactive configuration management
- Real-time progress tracking
- Database connection testing
- GPT integration controls
- Advanced filtering and sorting options
- Export capabilities
- Comprehensive statistics dashboard
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import numpy as np
import pandas as pd
from pymongo import MongoClient
import json
from datetime import datetime, date
from dateutil import parser
from collections import defaultdict, Counter
from typing import List, Dict, Tuple, Optional  
import os
import sys
import time
import re
import threading
from queue import Queue, Empty
from difflib import SequenceMatcher

# Add project root to Python path for utils imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from utils.gpt_cache import gpt_cache
    from utils.gpt_fallbacks import smart_statute_ordering, should_use_gpt_fallback
    from utils.gpt_rate_limiter import rate_limited_gpt_call
    from utils.gpt_prompt_optimizer import optimize_gpt_prompt
except ImportError:
    # Create mock classes if utils are not available
    class MockGPTCache:
        def get(self, key): return None
        def set(self, key, value): pass
    
    gpt_cache = MockGPTCache()
    
    def rate_limited_gpt_call(func):
        return func
    
    def optimize_gpt_prompt(func):
        return func

# Azure OpenAI imports
try:
    from openai import AzureOpenAI
except ImportError:
    AzureOpenAI = None

class StatuteVersioningGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Statute Versioning Tool - Advanced GUI")
        self.root.geometry("1400x900")
        self.root.configure(bg='#f0f0f0')
        
        # Initialize variables
        self.config = self.load_gui_config_file()
        self.client_mongo = None
        self.client_aoai = None
        self.source_col = None
        self.target_col = None
        self.processing_thread = None
        self.stop_processing = False
        self.progress_queue = Queue()
        
        # Metadata tracking
        self.metadata = {
            "total_groups_processed": 0,
            "total_statutes_versioned": 0,
            "versioning_stats": {
                "groups_with_single_version": 0,
                "groups_with_multiple_versions": 0,
                "max_versions_in_group": 0,
                "average_versions_per_group": 0,
                "total_versions_created": 0
            },
            "version_label_distribution": {
                "version_labels": Counter(),
                "date_analysis": defaultdict(list),
                "sample_versions": []
            },
            "processing_details": {
                "statutes_with_valid_dates": 0,
                "statutes_with_invalid_dates": 0,
                "statutes_with_missing_dates": 0,
                "date_parsing_errors": 0,
                "groups_created": 0,
                "database_updates": 0,
            },
            "gpt_usage": {
                "gpt_calls_made": 0,
                "gpt_cache_hits": 0,
                "gpt_errors": 0,
                "gpt_ordering_decisions": []
            }
        }
        
        # Comparison data for merge details
        self.comparison_data = {
            'merge_details': {},
            'group_details': {},
            'source_data': {},
            'target_data': {},
            'comparison_results': {},
            'approved_groups': set()
        }
        
        self.setup_gui()
        self.update_progress_display()
    
    def load_default_config(self):
        """Load default configuration"""
        return {
            "mongo_uri": "mongodb://localhost:27017",
            "source_db": "Batch-Base-Grouped-Filled",
            "source_collection": "batch1",
            "target_db": "Batch-Statute-Versioned-Filled",
            "target_collection": "batch1",
            "azure_api_key": "",
            "azure_endpoint": "",
            "gpt_model": "gpt-4o",
            "azure_api_version": "2024-11-01-preview",
            "enable_gpt_ordering": True,
            "enable_date_validation": True,
            "enable_province_aware_merging": True,
            "processing": {
                "batch_size": 1000,
                "max_workers": 4,
                "enable_gpt_disambiguation": True,
                "enable_timeline_visualization": True,
                "enable_progress_tracking": True,
                "date_formats": [
                    "%Y-%m-%d",
                    "%d-%m-%Y",
                    "%d/%m/%Y",
                    "%m/%d/%Y",
                    "%d-%b-%Y",
                    "%d %B %Y",
                    "%B %d, %Y"
                ]
            },
            "ui": {
                "window_width": 1400,
                "window_height": 900,
                "refresh_interval": 1000,
                "max_log_entries": 1000,
                "auto_save_interval": 300,
                "timeline_height": 400,
                "details_height": 200
            },
            "export": {
                "default_format": "json",
                "include_metadata": True,
                "include_version_details": True,
                "include_gpt_analysis": True,
                "include_date_validation": True
            },
            "logging": {
                "level": "INFO",
                "file_output": True,
                "console_output": True,
                "max_file_size": "10MB"
            },
            "versioning": {
                "default_labels": [
                    "Original",
                    "First Amendment",
                    "Second Amendment",
                    "Third Amendment"
                ],
                "confidence_threshold": 0.7,
                "enable_manual_override": True,
                "enable_conflict_resolution": True
            }
        }
    
    def load_gui_config_file(self):
        """Load configuration from gui/config_statute_versioning.json"""
        config_file = "gui/config_statute_versioning.json"
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            return config
        except FileNotFoundError:
            print(f"Config file {config_file} not found, using defaults")
            return self.load_default_config()
        except Exception as e:
            print(f"Error loading config file {config_file}: {e}")
            return self.load_default_config()
    
    def sync_target_collection(self):
        """Ensure target collection matches source collection"""
        source_collection = self.source_collection_var.get()
        self.target_collection_var.set(source_collection)
    
    def setup_gui(self):
        """Setup the main GUI interface"""
        # Create main notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Setup tabs
        self.setup_config_tab()
        self.setup_processing_tab()
        self.setup_comparison_tab()
        self.setup_statistics_tab()
        self.setup_logs_tab()
        
        # Status bar
        self.setup_status_bar()
    
    def setup_config_tab(self):
        """Setup configuration tab"""
        config_frame = ttk.Frame(self.notebook)
        self.notebook.add(config_frame, text="Configuration")
        
        # Database Configuration
        db_frame = ttk.LabelFrame(config_frame, text="Database Configuration", padding=10)
        db_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # MongoDB URI
        ttk.Label(db_frame, text="MongoDB URI:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.mongo_uri_var = tk.StringVar(value=self.config["mongo_uri"])
        mongo_uri_entry = ttk.Entry(db_frame, textvariable=self.mongo_uri_var, width=50)
        mongo_uri_entry.grid(row=0, column=1, columnspan=2, sticky=tk.EW, pady=2)
        
        # Source Database
        ttk.Label(db_frame, text="Source Database:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.source_db_var = tk.StringVar(value=self.config["source_db"])
        ttk.Entry(db_frame, textvariable=self.source_db_var, width=30).grid(row=1, column=1, sticky=tk.EW, pady=2)
        
        # Source Collection
        ttk.Label(db_frame, text="Source Collection:").grid(row=1, column=2, sticky=tk.W, pady=2, padx=(10,0))
        self.source_collection_var = tk.StringVar(value=self.config["source_collection"])
        source_combo = ttk.Combobox(db_frame, textvariable=self.source_collection_var, 
                                   values=[f"batch{i}" for i in range(1, 11)], width=20)
        source_combo.grid(row=1, column=3, sticky=tk.EW, pady=2)
        source_combo.bind('<<ComboboxSelected>>', lambda e: self.sync_target_collection())
        
        # Target Database
        ttk.Label(db_frame, text="Target Database:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.target_db_var = tk.StringVar(value=self.config["target_db"])
        ttk.Entry(db_frame, textvariable=self.target_db_var, width=30).grid(row=2, column=1, sticky=tk.EW, pady=2)
        
        # Target Collection
        ttk.Label(db_frame, text="Target Collection:").grid(row=2, column=2, sticky=tk.W, pady=2, padx=(10,0))
        self.target_collection_var = tk.StringVar(value=self.config["target_collection"])
        ttk.Entry(db_frame, textvariable=self.target_collection_var, width=20).grid(row=2, column=3, sticky=tk.EW, pady=2)
        
        # Test Connection Button
        ttk.Button(db_frame, text="Test Connection", command=self.test_database_connection).grid(row=3, column=0, pady=10)
        self.db_status_label = ttk.Label(db_frame, text="Not Connected", foreground="red")
        self.db_status_label.grid(row=3, column=1, sticky=tk.W, pady=10)
        
        # GPT Configuration
        gpt_frame = ttk.LabelFrame(config_frame, text="GPT Configuration", padding=10)
        gpt_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Azure API Key
        ttk.Label(gpt_frame, text="Azure API Key:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.azure_api_key_var = tk.StringVar(value=self.config["azure_api_key"])
        api_key_entry = ttk.Entry(gpt_frame, textvariable=self.azure_api_key_var, show="*", width=50)
        api_key_entry.grid(row=0, column=1, columnspan=2, sticky=tk.EW, pady=2)
        
        # Azure Endpoint
        ttk.Label(gpt_frame, text="Azure Endpoint:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.azure_endpoint_var = tk.StringVar(value=self.config["azure_endpoint"])
        ttk.Entry(gpt_frame, textvariable=self.azure_endpoint_var, width=50).grid(row=1, column=1, columnspan=2, sticky=tk.EW, pady=2)
        
        # GPT Model
        ttk.Label(gpt_frame, text="GPT Model:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.gpt_model_var = tk.StringVar(value=self.config["gpt_model"])
        model_combo = ttk.Combobox(gpt_frame, textvariable=self.gpt_model_var, values=["gpt-4o", "gpt-4", "gpt-3.5-turbo"])
        model_combo.grid(row=2, column=1, sticky=tk.EW, pady=2)
        
        # Test GPT Connection
        ttk.Button(gpt_frame, text="Test GPT Connection", command=self.test_gpt_connection).grid(row=3, column=0, pady=10)
        self.gpt_status_label = ttk.Label(gpt_frame, text="Not Connected", foreground="red")
        self.gpt_status_label.grid(row=3, column=1, sticky=tk.W, pady=10)
        
        # Processing Options
        options_frame = ttk.LabelFrame(config_frame, text="Processing Options", padding=10)
        options_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.use_gpt_var = tk.BooleanVar(value=self.config.get("enable_gpt_ordering", True))
        ttk.Checkbutton(options_frame, text="Use GPT for ambiguous ordering", variable=self.use_gpt_var).pack(anchor=tk.W)
        
        self.vectorized_var = tk.BooleanVar(value=self.config.get("enable_vectorized_processing", True))
        ttk.Checkbutton(options_frame, text="Enable vectorized processing (NumPy)", variable=self.vectorized_var).pack(anchor=tk.W)
        
        self.cache_gpt_var = tk.BooleanVar(value=self.config.get("cache_gpt_results", True))
        ttk.Checkbutton(options_frame, text="Cache GPT results", variable=self.cache_gpt_var).pack(anchor=tk.W)
        
        # Province-aware merging option
        self.province_aware_merging_var = tk.BooleanVar(value=self.config.get("enable_province_aware_merging", True))
        ttk.Checkbutton(options_frame, text="Enable province-aware merging (prevents cross-province merges)", 
                       variable=self.province_aware_merging_var).pack(anchor=tk.W)
        
        # Batch Size
        batch_frame = ttk.Frame(options_frame)
        batch_frame.pack(fill=tk.X, pady=5)
        ttk.Label(batch_frame, text="Batch Size:").pack(side=tk.LEFT)
        self.batch_size_var = tk.IntVar(value=self.config.get("processing", {}).get("batch_size", 1000))
        ttk.Spinbox(batch_frame, from_=100, to=10000, textvariable=self.batch_size_var, width=10).pack(side=tk.LEFT, padx=5)
        
        # Config buttons
        config_buttons_frame = ttk.Frame(config_frame)
        config_buttons_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(config_buttons_frame, text="Load Config", command=self.load_config_file).pack(side=tk.LEFT, padx=5)
        ttk.Button(config_buttons_frame, text="Save Config", command=self.save_config_file).pack(side=tk.LEFT, padx=5)
        ttk.Button(config_buttons_frame, text="Reset to Defaults", command=self.reset_config).pack(side=tk.LEFT, padx=5)
    
    def setup_processing_tab(self):
        """Setup processing tab"""
        processing_frame = ttk.Frame(self.notebook)
        self.notebook.add(processing_frame, text="Processing")
        
        # Processing controls
        controls_frame = ttk.LabelFrame(processing_frame, text="Processing Controls", padding=10)
        controls_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Start/Stop buttons
        button_frame = ttk.Frame(controls_frame)
        button_frame.pack(fill=tk.X, pady=5)
        
        self.start_button = ttk.Button(button_frame, text="Start Processing", command=self.start_processing)
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(button_frame, text="Stop Processing", command=self.stop_processing_func, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        # Export merge details button
        self.export_merge_button = ttk.Button(button_frame, text="Export Merge Details", command=self.export_merge_details, state=tk.DISABLED)
        self.export_merge_button.pack(side=tk.LEFT, padx=5)
        
        # Show merge summary button
        self.merge_summary_button = ttk.Button(button_frame, text="Show Merge Summary", command=self.show_merge_summary, state=tk.DISABLED)
        self.merge_summary_button.pack(side=tk.LEFT, padx=5)
        
        # Load comparison button
        self.load_comparison_button = ttk.Button(button_frame, text="Load Comparison", command=self.load_collections_for_comparison, state=tk.DISABLED)
        self.load_comparison_button.pack(side=tk.LEFT, padx=5)
        
        # Progress bar
        progress_frame = ttk.Frame(controls_frame)
        progress_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(progress_frame, text="Progress:").pack(anchor=tk.W)
        self.progress_bar = ttk.Progressbar(progress_frame, mode='determinate')
        self.progress_bar.pack(fill=tk.X, pady=2)
        
        self.progress_label = ttk.Label(progress_frame, text="Ready")
        self.progress_label.pack(anchor=tk.W)
        
        # Statistics display
        stats_frame = ttk.LabelFrame(processing_frame, text="Processing Statistics", padding=10)
        stats_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Statistics treeview
        stats_columns = ("Metric", "Value")
        self.stats_tree = ttk.Treeview(stats_frame, columns=stats_columns, show="headings", height=15)
        self.stats_tree.heading("Metric", text="Metric")
        self.stats_tree.heading("Value", text="Value")
        self.stats_tree.column("Metric", width=200)
        self.stats_tree.column("Value", width=150)
        self.stats_tree.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbar for stats
        stats_scrollbar = ttk.Scrollbar(stats_frame, orient=tk.VERTICAL, command=self.stats_tree.yview)
        stats_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.stats_tree.configure(yscrollcommand=stats_scrollbar.set)
    
    def setup_comparison_tab(self):
        """Setup comparison tab for side-by-side collection comparison"""
        comparison_frame = ttk.Frame(self.notebook)
        self.notebook.add(comparison_frame, text="Collection Comparison")
        
        # Control Panel
        control_frame = ttk.LabelFrame(comparison_frame, text="Comparison Control", padding=10)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Collection selection frame
        collection_frame = ttk.Frame(control_frame)
        collection_frame.pack(fill=tk.X, pady=5)
        
        # Source collection info
        source_info_frame = ttk.LabelFrame(collection_frame, text="Source Collection", padding=5)
        source_info_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        ttk.Label(source_info_frame, text=f"Database: {self.config['source_db']}").pack(anchor=tk.W)
        ttk.Label(source_info_frame, text=f"Collection: {self.config['source_collection']}").pack(anchor=tk.W)
        
        # Target collection info
        target_info_frame = ttk.LabelFrame(collection_frame, text="Target Collection", padding=5)
        target_info_frame.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(5, 0))
        
        ttk.Label(target_info_frame, text=f"Database: {self.config['target_db']}").pack(anchor=tk.W)
        ttk.Label(target_info_frame, text=f"Collection: {self.config['target_collection']}").pack(anchor=tk.W)
        
        # Comparison buttons
        buttons_frame = ttk.Frame(control_frame)
        buttons_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(buttons_frame, text="Load Collections", command=self.load_collections_for_comparison).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Compare Collections", command=self.compare_collections).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Export Comparison", command=self.export_comparison).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Clear Comparison", command=self.clear_comparison).pack(side=tk.LEFT, padx=5)
        
        # Approval buttons
        approval_frame = ttk.LabelFrame(control_frame, text="Approval Actions", padding=5)
        approval_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(approval_frame, text="Approve All Selected", command=self.approve_selected_groups).pack(side=tk.LEFT, padx=5)
        ttk.Button(approval_frame, text="Approve All", command=self.approve_all_groups).pack(side=tk.LEFT, padx=5)
        ttk.Button(approval_frame, text="Reject All", command=self.reject_all_groups).pack(side=tk.LEFT, padx=5)
        ttk.Button(approval_frame, text="Save Approved to DB", command=self.save_approved_to_database).pack(side=tk.LEFT, padx=5)
        
        # Comparison results frame
        results_frame = ttk.LabelFrame(comparison_frame, text="Comparison Results", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Create paned window for side-by-side view
        paned_window = ttk.PanedWindow(results_frame, orient=tk.HORIZONTAL)
        paned_window.pack(fill=tk.BOTH, expand=True)
        
        # Left panel - Source collection
        left_frame = ttk.Frame(paned_window)
        paned_window.add(left_frame, weight=1)
        
        ttk.Label(left_frame, text="Source Collection Data", font=("Arial", 10, "bold")).pack(pady=5)
        
        # Source treeview with expandable groups
        source_columns = ("Group Name", "Statute Count", "Status")
        self.source_tree = ttk.Treeview(left_frame, columns=source_columns, show="tree headings", height=20)
        
        for col in source_columns:
            self.source_tree.heading(col, text=col)
            self.source_tree.column(col, width=150)
        
        source_scrollbar = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.source_tree.yview)
        self.source_tree.configure(yscrollcommand=source_scrollbar.set)
        
        self.source_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        source_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Right panel - Target collection
        right_frame = ttk.Frame(paned_window)
        paned_window.add(right_frame, weight=1)
        
        ttk.Label(right_frame, text="Target Collection Data", font=("Arial", 10, "bold")).pack(pady=5)
        
        # Target treeview with expandable groups and checkboxes
        target_columns = ("Select", "Group Name", "Statutes Count", "Versions", "Status")
        self.target_tree = ttk.Treeview(right_frame, columns=target_columns, show="tree headings", height=20)
        
        for col in target_columns:
            self.target_tree.heading(col, text=col)
            self.target_tree.column(col, width=100)
        
        target_scrollbar = ttk.Scrollbar(right_frame, orient=tk.VERTICAL, command=self.target_tree.yview)
        self.target_tree.configure(yscrollcommand=target_scrollbar.set)
        
        self.target_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        target_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind double-click to toggle selection
        self.target_tree.bind("<Double-1>", self.toggle_group_selection)
        
        # Bind selection events to show details
        self.source_tree.bind("<<TreeviewSelect>>", self.show_group_details)
        self.target_tree.bind("<<TreeviewSelect>>", self.show_group_details)
        
        # Configure tree styling
        self.source_tree.tag_configure('group', background='#f0f0f0', font=('Arial', 9, 'bold'))
        self.source_tree.tag_configure('statute', background='#ffffff', font=('Arial', 8))
        self.source_tree.tag_configure('more', background='#e8e8e8', font=('Arial', 8, 'italic'))
        
        self.target_tree.tag_configure('group', background='#f0f0f0', font=('Arial', 9, 'bold'))
        self.target_tree.tag_configure('version', background='#ffffff', font=('Arial', 8))
        self.target_tree.tag_configure('more', background='#e8e8e8', font=('Arial', 8, 'italic'))
        
        # Summary frame at bottom
        summary_frame = ttk.LabelFrame(comparison_frame, text="Comparison Summary", padding=10)
        summary_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.summary_text = scrolledtext.ScrolledText(summary_frame, wrap=tk.WORD, height=8)
        self.summary_text.pack(fill=tk.BOTH, expand=True)
        
        # Initialize comparison data
        self.comparison_data = {
            'source_data': {},
            'target_data': {},
            'comparison_results': {},
            'approved_groups': set(),
            'group_details': {}
        }
    
    def setup_statistics_tab(self):
        """Setup statistics tab"""
        stats_frame = ttk.Frame(self.notebook)
        self.notebook.add(stats_frame, text="Statistics")
        
        # Statistics display
        self.stats_text = scrolledtext.ScrolledText(stats_frame, wrap=tk.WORD, height=30)
        self.stats_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Add initial helpful message
        initial_stats_message = """📊 STATISTICS TAB - SUMMARY DATA

This tab shows summary statistics only.

📋 SUMMARY INCLUDES:
- Source collection overview
- Target collection summary
- Versioning summary
- Processing summary
- GPT usage summary

📋 DETAILED INFORMATION:
For comprehensive processing, merging, and versioning details, 
please check the Logs tab and set log level to 'DEBUG'.

💡 TIP: Use the "Show Processing Report" button in the Logs tab 
to see detailed statistics anytime.
"""
        self.stats_text.insert(tk.END, initial_stats_message)
        
        # Statistics control buttons
        stats_buttons_frame = ttk.Frame(stats_frame)
        stats_buttons_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(stats_buttons_frame, text="Refresh Statistics", command=self.refresh_statistics).pack(side=tk.LEFT, padx=5)
        ttk.Button(stats_buttons_frame, text="Export Statistics", command=self.export_statistics).pack(side=tk.LEFT, padx=5)
        ttk.Button(stats_buttons_frame, text="Clear Display", command=self.clear_statistics).pack(side=tk.LEFT, padx=5)
    
    def setup_logs_tab(self):
        """Setup logs tab"""
        logs_frame = ttk.Frame(self.notebook)
        self.notebook.add(logs_frame, text="Logs")
        
        # Log display
        self.log_text = scrolledtext.ScrolledText(logs_frame, wrap=tk.WORD, height=30)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Add initial helpful message
        initial_message = """📋 LOGS TAB - COMPREHENSIVE PROCESSING INFORMATION

This tab shows detailed processing, merging, and versioning information.

🔍 LOG LEVELS:
- DEBUG: Most detailed information (recommended for troubleshooting)
- INFO: General processing information and comprehensive reports
- WARNING: Important warnings and issues
- ERROR: Error messages only

📊 COMPREHENSIVE REPORTS:
After processing completes, a detailed report will appear here showing:
- Source collection statistics
- Target collection details  
- Versioning statistics
- Processing details
- GPT usage statistics
- Version label distribution
- Recent GPT ordering decisions

💡 TIP: Set log level to 'DEBUG' to see all processing details in real-time.
"""
        self.log_text.insert(tk.END, initial_message)
        
        # Log control buttons
        log_buttons_frame = ttk.Frame(logs_frame)
        log_buttons_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(log_buttons_frame, text="Clear Logs", command=self.clear_logs).pack(side=tk.LEFT, padx=5)
        ttk.Button(log_buttons_frame, text="Save Logs", command=self.save_logs).pack(side=tk.LEFT, padx=5)
        ttk.Button(log_buttons_frame, text="Show Processing Report", command=self._log_comprehensive_processing_details).pack(side=tk.LEFT, padx=5)
        
        # Log level selection
        ttk.Label(log_buttons_frame, text="Log Level:").pack(side=tk.LEFT, padx=(20, 5))
        self.log_level_var = tk.StringVar(value="INFO")
        log_level_combo = ttk.Combobox(log_buttons_frame, textvariable=self.log_level_var, values=["DEBUG", "INFO", "WARNING", "ERROR"])
        log_level_combo.pack(side=tk.LEFT, padx=5)
    
    def setup_status_bar(self):
        """Setup status bar"""
        self.status_frame = ttk.Frame(self.root)
        self.status_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=2)
        
        self.status_label = ttk.Label(self.status_frame, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.time_label = ttk.Label(self.status_frame, text="", relief=tk.SUNKEN)
        self.time_label.pack(side=tk.RIGHT)
        
        self.update_time()
    
    def update_time(self):
        """Update time display"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.time_label.config(text=current_time)
        self.root.after(1000, self.update_time)
    
    def log_message(self, message, level="INFO"):
        """Add message to log display"""
        if level in ["DEBUG"] and self.log_level_var.get() not in ["DEBUG"]:
            return
        if level in ["INFO"] and self.log_level_var.get() not in ["DEBUG", "INFO"]:
            return
        if level in ["WARNING"] and self.log_level_var.get() not in ["DEBUG", "INFO", "WARNING"]:
            return
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {level}: {message}\n"
        
        self.log_text.insert(tk.END, log_entry)
        self.log_text.see(tk.END)
        self.root.update_idletasks()
    
    def update_status(self, message):
        """Update status bar"""
        self.status_label.config(text=message)
        self.root.update_idletasks()
    
    def test_database_connection(self):
        """Test MongoDB connection"""
        try:
            self.update_status("Testing database connection...")
            
            client = MongoClient(self.mongo_uri_var.get(), serverSelectionTimeoutMS=5000)
            client.server_info()  # Force connection
            
            # Test collections
            source_db = client[self.source_db_var.get()]
            target_db = client[self.target_db_var.get()]
            
            source_count = source_db[self.source_collection_var.get()].count_documents({})
            
            self.db_status_label.config(text=f"Connected ({source_count} documents)", foreground="green")
            self.log_message(f"Database connection successful. Found {source_count} source documents.")
            self.update_status("Database connection successful")
            
            self.client_mongo = client
            self.source_db = source_db
            self.source_col = source_db[self.source_collection_var.get()]
            self.target_col = target_db[self.target_collection_var.get()]
            
        except Exception as e:
            self.db_status_label.config(text="Connection Failed", foreground="red")
            self.log_message(f"Database connection failed: {str(e)}", "ERROR")
            self.update_status("Database connection failed")
            messagebox.showerror("Connection Error", f"Failed to connect to database:\n{str(e)}")
    
    def test_gpt_connection(self):
        """Test GPT connection"""
        try:
            if not AzureOpenAI:
                raise ImportError("Azure OpenAI library not available")
            
            self.update_status("Testing GPT connection...")
            
            client = AzureOpenAI(
                api_key=self.azure_api_key_var.get(),
                api_version=self.config["azure_api_version"],
                azure_endpoint=self.azure_endpoint_var.get()
            )
            
            # Test with a simple request
            response = client.chat.completions.create(
                model=self.gpt_model_var.get(),
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5
            )
            
            self.gpt_status_label.config(text="Connected", foreground="green")
            self.log_message("GPT connection successful")
            self.update_status("GPT connection successful")
            self.client_aoai = client
            
        except Exception as e:
            self.gpt_status_label.config(text="Connection Failed", foreground="red")
            self.log_message(f"GPT connection failed: {str(e)}", "ERROR")
            self.update_status("GPT connection failed")
            messagebox.showerror("GPT Connection Error", f"Failed to connect to GPT:\n{str(e)}")
    
    def load_config_file(self):
        """Load configuration from file"""
        filename = filedialog.askopenfilename(
            title="Load Configuration",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, 'r') as f:
                    config = json.load(f)
                
                # Update variables
                self.mongo_uri_var.set(config.get("mongo_uri", ""))
                self.source_db_var.set(config.get("source_db", ""))
                self.source_collection_var.set(config.get("source_collection", ""))
                self.target_db_var.set(config.get("target_db", ""))
                self.target_collection_var.set(config.get("target_collection", ""))
                self.azure_api_key_var.set(config.get("azure_api_key", ""))
                self.azure_endpoint_var.set(config.get("azure_endpoint", ""))
                self.gpt_model_var.set(config.get("gpt_model", "gpt-4o"))
                self.use_gpt_var.set(config.get("enable_gpt_ordering", True))
                self.vectorized_var.set(config.get("enable_vectorized_processing", True))
                self.cache_gpt_var.set(config.get("cache_gpt_results", True))
                self.province_aware_merging_var.set(config.get("enable_province_aware_merging", True))
                self.batch_size_var.set(config.get("processing", {}).get("batch_size", 1000))
                
                self.log_message(f"Configuration loaded from {filename}")
                messagebox.showinfo("Success", "Configuration loaded successfully!")
                
            except Exception as e:
                self.log_message(f"Failed to load configuration: {str(e)}", "ERROR")
                messagebox.showerror("Error", f"Failed to load configuration:\n{str(e)}")
    
    def save_config_file(self):
        """Save current configuration to file"""
        filename = filedialog.asksaveasfilename(
            title="Save Configuration",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                config = {
                    "mongo_uri": self.mongo_uri_var.get(),
                    "source_db": self.source_db_var.get(),
                    "source_collection": self.source_collection_var.get(),
                    "target_db": self.target_db_var.get(),
                    "target_collection": self.target_collection_var.get(),
                    "azure_api_key": self.azure_api_key_var.get(),
                    "azure_endpoint": self.azure_endpoint_var.get(),
                    "gpt_model": self.gpt_model_var.get(),
                    "azure_api_version": self.config["azure_api_version"],
                    "enable_gpt_ordering": self.use_gpt_var.get(),
                    "enable_vectorized_processing": self.vectorized_var.get(),
                    "cache_gpt_results": self.cache_gpt_var.get(),
                    "enable_province_aware_merging": self.province_aware_merging_var.get(),
                    "processing": {
                        "batch_size": self.batch_size_var.get()
                    }
                }
                
                with open(filename, 'w') as f:
                    json.dump(config, f, indent=2)
                
                self.log_message(f"Configuration saved to {filename}")
                messagebox.showinfo("Success", "Configuration saved successfully!")
                
            except Exception as e:
                self.log_message(f"Failed to save configuration: {str(e)}", "ERROR")
                messagebox.showerror("Error", f"Failed to save configuration:\n{str(e)}")
    
    def reset_config(self):
        """Reset configuration to defaults"""
        if messagebox.askyesno("Reset Configuration", "Are you sure you want to reset to default configuration?"):
            default_config = self.load_default_config()
            
            self.mongo_uri_var.set(default_config["mongo_uri"])
            self.source_db_var.set(default_config["source_db"])
            self.source_collection_var.set(default_config["source_collection"])
            self.target_db_var.set(default_config["target_db"])
            self.target_collection_var.set(default_config["target_collection"])
            self.azure_api_key_var.set(default_config["azure_api_key"])
            self.azure_endpoint_var.set(default_config["azure_endpoint"])
            self.gpt_model_var.set(default_config["gpt_model"])
            self.use_gpt_var.set(default_config["enable_gpt_ordering"])
            self.vectorized_var.set(default_config["enable_vectorized_processing"])
            self.cache_gpt_var.set(default_config["cache_gpt_results"])
            self.province_aware_merging_var.set(default_config["enable_province_aware_merging"])
            self.batch_size_var.set(default_config["processing"]["batch_size"])
            
            self.log_message("Configuration reset to defaults")
    
    def start_processing(self):
        """Start the processing in a separate thread"""
        if self.client_mongo is None or self.source_col is None or self.target_col is None:
            messagebox.showerror("Error", "Please test database connection first!")
            return
        
        if self.use_gpt_var.get() and not self.client_aoai:
            messagebox.showerror("Error", "GPT is enabled but not connected. Please test GPT connection first!")
            return
        
        self.stop_processing = False
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        
        # Start processing thread
        self.processing_thread = threading.Thread(target=self.process_statutes)
        self.processing_thread.daemon = True
        self.processing_thread.start()
        
        self.log_message("Started statute versioning process")
        self.update_status("Processing started...")
    
    def stop_processing_func(self):
        """Stop the processing"""
        self.stop_processing = True
        self.stop_button.config(state=tk.DISABLED)
        self.log_message("Stop signal sent. Please wait for current operation to complete...")
        self.update_status("Stopping process...")
    
    def update_progress_display(self):
        """Update progress display periodically"""
        try:
            while True:
                try:
                    progress_data = self.progress_queue.get_nowait()
                    
                    if progress_data['type'] == 'progress':
                        self.progress_bar['value'] = progress_data['value']
                        self.progress_label.config(text=progress_data['message'])
                    elif progress_data['type'] == 'complete':
                        self.start_button.config(state=tk.NORMAL)
                        self.stop_button.config(state=tk.DISABLED)
                        self.progress_bar['value'] = 100
                        self.progress_label.config(text="Processing completed!")
                        self.update_status("Processing completed")
                        self.refresh_statistics()
                    elif progress_data['type'] == 'error':
                        self.start_button.config(state=tk.NORMAL)
                        self.stop_button.config(state=tk.DISABLED)
                        self.progress_label.config(text=f"Error: {progress_data['message']}")
                        self.update_status("Processing failed")
                    elif progress_data['type'] == 'stats':
                        self.update_stats_tree(progress_data['stats'])
                    elif progress_data['type'] == 'enable_export':
                        self.export_merge_button.config(state=tk.NORMAL)
                        self.merge_summary_button.config(state=tk.NORMAL)
                        self.load_comparison_button.config(state=tk.NORMAL)
                        
                except Empty:
                    break
        except:
            pass
        
        self.root.after(500, self.update_progress_display)
    
    def update_stats_tree(self, stats):
        """Update statistics tree view"""
        # Clear existing items
        for item in self.stats_tree.get_children():
            self.stats_tree.delete(item)
        
        # Handle both old format (direct stats) and new format (combined stats)
        if isinstance(stats, dict) and 'source_stats' in stats and 'target_stats' in stats:
            # New combined format
            source_stats = stats['source_stats']
            target_stats = stats['target_stats']
        else:
            # Old format - use source_stats if available, otherwise empty
            source_stats = getattr(self, 'source_stats', {})
            target_stats = stats
        
        # Add source statistics if available
        if source_stats:
            self.stats_tree.insert("", "end", values=("", ""))  # Empty row for spacing
            self.stats_tree.insert("", "end", values=("SOURCE COLLECTION", ""))
            self.stats_tree.insert("", "end", values=("Collection", source_stats.get("source_collection", "Unknown")))
            self.stats_tree.insert("", "end", values=("Total Groups", source_stats.get("total_groups", 0)))
            self.stats_tree.insert("", "end", values=("Total Statutes", source_stats.get("total_statutes", 0)))
            self.stats_tree.insert("", "end", values=("Groups with Statutes", source_stats.get("groups_with_statutes", 0)))
            self.stats_tree.insert("", "end", values=("Groups without Statutes", source_stats.get("groups_without_statutes", 0)))
            self.stats_tree.insert("", "end", values=("Documents Processed", source_stats.get("documents_processed", 0)))
            self.stats_tree.insert("", "end", values=("Documents Merged", source_stats.get("documents_merged", 0)))
            self.stats_tree.insert("", "end", values=("", ""))  # Empty row for spacing
        
        # Add target statistics
        self.stats_tree.insert("", "end", values=("TARGET COLLECTION", ""))
        self.stats_tree.insert("", "end", values=("Total Groups Processed", target_stats.get("total_groups_processed", 0)))
        self.stats_tree.insert("", "end", values=("Total Statutes Versioned", target_stats.get("total_statutes_versioned", 0)))
        
        # Versioning stats
        versioning_stats = target_stats.get("versioning_stats", {})
        self.stats_tree.insert("", "end", values=("Groups with Single Version", versioning_stats.get("groups_with_single_version", 0)))
        self.stats_tree.insert("", "end", values=("Groups with Multiple Versions", versioning_stats.get("groups_with_multiple_versions", 0)))
        self.stats_tree.insert("", "end", values=("Max Versions in Group", versioning_stats.get("max_versions_in_group", 0)))
        self.stats_tree.insert("", "end", values=("Average Versions per Group", f"{versioning_stats.get('average_versions_per_group', 0):.2f}"))
        
        # Processing details
        processing_details = target_stats.get("processing_details", {})
        self.stats_tree.insert("", "end", values=("Valid Dates", processing_details.get("statutes_with_valid_dates", 0)))
        self.stats_tree.insert("", "end", values=("Invalid Dates", processing_details.get("statutes_with_invalid_dates", 0)))
        self.stats_tree.insert("", "end", values=("Missing Dates", processing_details.get("statutes_with_missing_dates", 0)))
        
        # GPT usage
        gpt_usage = target_stats.get("gpt_usage", {})
        self.stats_tree.insert("", "end", values=("GPT Calls Made", gpt_usage.get("gpt_calls_made", 0)))
        self.stats_tree.insert("", "end", values=("GPT Cache Hits", gpt_usage.get("gpt_cache_hits", 0)))
        self.stats_tree.insert("", "end", values=("GPT Errors", gpt_usage.get("gpt_errors", 0)))
    
    def process_statutes(self):
        """Main processing function running in separate thread"""
        try:
            self.progress_queue.put({'type': 'progress', 'value': 0, 'message': 'Loading grouped statutes...'})
            
            # Load groupings
            groupings = self.load_groupings_from_database()
            if not groupings:
                groupings = self.group_statutes_from_database()
            
            if not groupings:
                self.progress_queue.put({'type': 'error', 'message': 'No groupings found'})
                return
            
            self.progress_queue.put({'type': 'progress', 'value': 10, 'message': f'Found {len(groupings)} base groups'})
            
            # Process versioning
            versioned_groupings = self.assign_version_labels_vectorized(groupings)
            
            self.progress_queue.put({'type': 'progress', 'value': 80, 'message': 'Preparing versioned data for review...'})
            
            # Store versioned data in memory for approval instead of creating database immediately
            self.pending_versioned_data = versioned_groupings
            
            # Calculate statistics for display
            created_count = len(versioned_groupings)
            total_statutes_versioned = sum(len(statutes) for statutes in versioned_groupings.values())
            
            self.progress_queue.put({'type': 'progress', 'value': 90, 'message': 'Preparing comparison data...'})
            
            # Update metadata for display (but don't save yet)
            self.metadata["total_groups_processed"] = created_count
            self.metadata["total_statutes_versioned"] = total_statutes_versioned
            
            self.progress_queue.put({'type': 'progress', 'value': 100, 'message': f'Ready for review! Created {created_count} versioned groups'})
            self.progress_queue.put({'type': 'complete', 'message': 'Processing completed - ready for approval'})
            
            # Update statistics display with both source and target data
            if hasattr(self, 'source_stats'):
                # Combine source and target statistics for display
                combined_stats = {
                    'source_stats': self.source_stats,
                    'target_stats': {
                        'total_groups_processed': self.metadata.get('total_groups_processed', 0),
                        'total_statutes_versioned': self.metadata.get('total_statutes_versioned', 0),
                        'versioning_stats': self.metadata.get('versioning_stats', {}),
                        'processing_details': self.metadata.get('processing_details', {}),
                        'gpt_usage': self.metadata.get('gpt_usage', {})
                    }
                }
                self.progress_queue.put({'type': 'stats', 'stats': combined_stats})
                
                # Store merge details for export functionality
                if hasattr(self, 'source_stats') and 'merge_details' in self.source_stats:
                    self.comparison_data = {
                        'merge_details': self.source_stats['merge_details']
                    }
                    self.progress_queue.put({'type': 'enable_export'})
            
            self._log_comprehensive_processing_details()
            
        except Exception as e:
            self.log_message(f"Processing error: {str(e)}", "ERROR")
            self.progress_queue.put({'type': 'error', 'message': str(e)})
    
    def _log_comprehensive_processing_details(self):
        """Log comprehensive processing, merging, and versioning details to logs tab"""
        try:
            self.log_message("=" * 80, "INFO")
            self.log_message("COMPREHENSIVE PROCESSING, MERGING, AND VERSIONING REPORT", "INFO")
            self.log_message("=" * 80, "INFO")
            
            # Source collection details
            if hasattr(self, 'source_stats') and self.source_stats:
                self.log_message("📊 SOURCE COLLECTION DETAILS:", "INFO")
                self.log_message(f"   Collection: {self.source_stats.get('source_collection', 'Unknown')}", "INFO")
                self.log_message(f"   Total groups: {self.source_stats.get('total_groups', 0)}", "INFO")
                self.log_message(f"   Total statutes: {self.source_stats.get('total_statutes', 0)}", "INFO")
                self.log_message(f"   Groups with statutes: {self.source_stats.get('groups_with_statutes', 0)}", "INFO")
                self.log_message(f"   Groups without statutes: {self.source_stats.get('groups_without_statutes', 0)}", "INFO")
                self.log_message(f"   Documents processed: {self.source_stats.get('documents_processed', 0)}", "INFO")
                self.log_message(f"   Documents merged: {self.source_stats.get('documents_merged', 0)}", "INFO")
                self.log_message("", "INFO")
            
            # Target collection details
            self.log_message("📊 TARGET COLLECTION DETAILS:", "INFO")
            self.log_message(f"   Total groups processed: {self.metadata['total_groups_processed']}", "INFO")
            self.log_message(f"   Total statutes versioned: {self.metadata['total_statutes_versioned']}", "INFO")
            self.log_message(f"   Groups created: {self.metadata['processing_details']['groups_created']}", "INFO")
            self.log_message("", "INFO")
            
            # Versioning statistics
            versioning_stats = self.metadata['versioning_stats']
            self.log_message("📊 VERSIONING STATISTICS:", "INFO")
            self.log_message(f"   Groups with single version: {versioning_stats['groups_with_single_version']}", "INFO")
            self.log_message(f"   Groups with multiple versions: {versioning_stats['groups_with_multiple_versions']}", "INFO")
            self.log_message(f"   Max versions in a group: {versioning_stats['max_versions_in_group']}", "INFO")
            self.log_message(f"   Average versions per group: {versioning_stats['average_versions_per_group']:.2f}", "INFO")
            self.log_message(f"   Total versions created: {versioning_stats['total_versions_created']}", "INFO")
            self.log_message("", "INFO")
            
            # Processing details
            processing_details = self.metadata['processing_details']
            self.log_message("📊 PROCESSING DETAILS:", "INFO")
            self.log_message(f"   Statutes with valid dates: {processing_details['statutes_with_valid_dates']}", "INFO")
            self.log_message(f"   Statutes with invalid dates: {processing_details['statutes_with_invalid_dates']}", "INFO")
            self.log_message(f"   Statutes with missing dates: {processing_details['statutes_with_missing_dates']}", "INFO")
            self.log_message(f"   Date parsing errors: {processing_details['date_parsing_errors']}", "INFO")
            self.log_message(f"   Database updates: {processing_details['database_updates']}", "INFO")
            self.log_message("", "INFO")
            
            # GPT usage statistics
            gpt_usage = self.metadata['gpt_usage']
            self.log_message("📊 GPT USAGE STATISTICS:", "INFO")
            self.log_message(f"   GPT calls made: {gpt_usage['gpt_calls_made']}", "INFO")
            self.log_message(f"   GPT cache hits: {gpt_usage['gpt_cache_hits']}", "INFO")
            self.log_message(f"   GPT errors: {gpt_usage['gpt_errors']}", "INFO")
            self.log_message("", "INFO")
            
            # Version label distribution
            version_labels = self.metadata["version_label_distribution"]["version_labels"]
            if version_labels:
                self.log_message("📊 VERSION LABEL DISTRIBUTION:", "INFO")
                for version_label, count in version_labels.most_common(10):
                    self.log_message(f"   {version_label}: {count} statutes", "INFO")
                self.log_message("", "INFO")
            
            # Recent GPT ordering decisions
            if self.metadata["gpt_usage"]["gpt_ordering_decisions"]:
                self.log_message("📊 RECENT GPT ORDERING DECISIONS:", "INFO")
                for i, decision in enumerate(self.metadata["gpt_usage"]["gpt_ordering_decisions"][-10:]):
                    self.log_message(f"   {i+1}. {decision['group']}: {decision['gpt_order']} - {decision['gpt_reason'][:50]}...", "INFO")
                self.log_message("", "INFO")
            
            self.log_message("=" * 80, "INFO")
            self.log_message("END OF COMPREHENSIVE REPORT", "INFO")
            self.log_message("=" * 80, "INFO")
            
        except Exception as e:
            self.log_message(f"Error logging comprehensive details: {str(e)}", "ERROR")
    
    def load_groupings_from_database(self) -> Dict[str, List[Dict]]:
        """Load grouped statutes from database"""
        try:
            source_collection_name = self.source_collection_var.get()
            
            # Get group documents from the specified source collection
            groupings = {}
            total_statutes_loaded = 0
            groups_with_statutes = 0
            groups_without_statutes = 0
            documents_processed = 0
            documents_merged = 0
            
            # Track merge details for detailed reporting
            merge_details = {}
            
            try:
                source_col = self.source_db[source_collection_name]
                group_documents = list(source_col.find({}))
                
                self.log_message(f"Found {len(group_documents)} group documents in {source_collection_name}")
                
                # Convert group documents to the expected format
                for group_doc in group_documents:
                    if self.stop_processing:
                        break
                        
                    base_name = group_doc.get("base_name", "Unknown")
                    statutes = group_doc.get("statutes", [])
                    documents_processed += 1
                    
                    # Track document details for merge reporting
                    doc_id = group_doc.get("_id", f"doc_{documents_processed}")
                    doc_info = {
                        "doc_id": str(doc_id),
                        "statute_count": len(statutes),
                        "statute_names": [s.get("Statute_Name", "Unknown") for s in statutes],
                        "statute_dates": [s.get("Date", "No date") for s in statutes],
                        "statute_types": [s.get("Statute_Type", "Unknown") for s in statutes]
                    }
                    
                    # Check for similar base_names and merge if similarity is high enough
                    best_match = None
                    best_similarity = 0.0
                    similarity_threshold = 0.85  # High threshold for grouping
                    
                    # Get province information for current group
                    current_province = normalize_province(group_doc.get("province", ""))
                    
                    for existing_base_name in groupings.keys():
                        similarity = calculate_similarity(base_name, existing_base_name)
                        
                        # Province-aware merging check
                        should_merge = True
                        merge_reason = ""
                        
                        if self.province_aware_merging_var.get():
                            # Get province from existing group (first statute's province)
                            existing_province = ""
                            if groupings[existing_base_name]:
                                existing_province = normalize_province(groupings[existing_base_name][0].get("Province", ""))
                            
                            # Check if provinces match
                            if current_province != existing_province:
                                should_merge = False
                                merge_reason = f"Province mismatch: '{current_province}' vs '{existing_province}'"
                        
                        if similarity > best_similarity and similarity >= similarity_threshold:
                            if should_merge:
                                best_similarity = similarity
                                best_match = existing_base_name
                            else:
                                # Log province mismatch
                                self.log_message(f"Province check prevented merge: '{base_name}' vs '{existing_base_name}' - {merge_reason}", "DEBUG")
                    
                    if best_match:
                        # Merge with existing group
                        existing_statutes = groupings[best_match]
                        original_count = len(existing_statutes)
                        groupings[best_match] = existing_statutes + statutes
                        documents_merged += 1
                        
                        # Track merge details
                        if best_match not in merge_details:
                            merge_details[best_match] = {
                                "first_doc": doc_info,
                                "merged_docs": []
                            }
                        else:
                            merge_details[best_match]["merged_docs"].append(doc_info)
                        
                        province_info = f" (Province: {current_province})" if current_province else ""
                        self.log_message(f"Group '{best_match}' (similarity: {best_similarity:.2f}): Merged '{base_name}'{province_info} with {len(statutes)} statutes (total: {len(groupings[best_match])})", "DEBUG")
                        self.log_message(f"  - Document {doc_id}: {len(statutes)} statutes", "DEBUG")
                    else:
                        # New base_name - add to groupings
                        groupings[base_name] = statutes
                        merge_details[base_name] = {
                            "first_doc": doc_info,
                            "merged_docs": []
                        }
                        self.log_message(f"Group '{base_name}': Added {len(statutes)} statutes", "DEBUG")
                        self.log_message(f"  - Document {doc_id}: {len(statutes)} statutes", "DEBUG")
                    
                    total_statutes_loaded += len(statutes)
                    
                    if statutes:
                        groups_with_statutes += 1
                    else:
                        groups_without_statutes += 1
                            
            except Exception as e:
                self.log_message(f"Error loading from {source_collection_name}: {str(e)}", "ERROR")
                return {}
            
            # Store source statistics for display
            self.source_stats = {
                "total_groups": len(groupings),
                "total_statutes": total_statutes_loaded,
                "groups_with_statutes": groups_with_statutes,
                "groups_without_statutes": groups_without_statutes,
                "source_collection": source_collection_name,
                "documents_processed": documents_processed,
                "documents_merged": documents_merged,
                "merge_details": merge_details
            }
            
            self.log_message(f"Loaded {len(groupings)} unique base groups from {source_collection_name}")
            self.log_message(f"Processed {documents_processed} documents, merged {documents_merged} documents with duplicate base_names")
            self.log_message(f"Groups with statutes: {groups_with_statutes}, Groups without statutes: {groups_without_statutes}")
            self.log_message(f"Total statutes loaded: {total_statutes_loaded}")
            
            # Log detailed merge information
            self._log_merge_details(merge_details)
            
            return groupings
            
        except Exception as e:
            self.log_message(f"Error loading groupings: {str(e)}", "ERROR")
            return {}
    
    def _log_merge_details(self, merge_details):
        """Log detailed information about merged documents"""
        if not merge_details:
            return
            
        self.log_message("=" * 60, "INFO")
        self.log_message("DETAILED MERGE REPORT", "INFO")
        self.log_message("=" * 60, "INFO")
        
        # Calculate summary statistics
        total_groups = len(merge_details)
        groups_with_merges = sum(1 for details in merge_details.values() if details["merged_docs"])
        total_merged_docs = sum(len(details["merged_docs"]) for details in merge_details.values())
        
        self.log_message(f"MERGE SUMMARY:", "INFO")
        self.log_message(f"  Total groups: {total_groups}", "INFO")
        self.log_message(f"  Groups with merges: {groups_with_merges}", "INFO")
        self.log_message(f"  Total documents merged: {total_merged_docs}", "INFO")
        self.log_message("", "INFO")
        
        # Explain the merge logic
        self.log_message("MERGE LOGIC EXPLANATION:", "INFO")
        self.log_message("  1. Documents are grouped by 'base_name' field from source collection", "INFO")
        self.log_message("  2. Similar base_names (similarity >= 0.85) are merged together", "INFO")
        self.log_message("  3. Similarity is calculated using SequenceMatcher algorithm", "INFO")
        self.log_message("  4. Text normalization removes punctuation and converts to lowercase", "INFO")
        self.log_message("  5. Example: 'Benazir Bhutto Shaheed University At Layari Karachi'", "INFO")
        self.log_message("     and 'Benazir Bhutto Shaheed University At Lyari Karachi'", "INFO")
        self.log_message("     would be merged due to high similarity (only 'Layari' vs 'Lyari')", "INFO")
        self.log_message("", "INFO")
        
        for base_name, details in merge_details.items():
            if details["merged_docs"]:  # Only show groups that had merges
                self.log_message(f"GROUP: {base_name}", "INFO")
                self.log_message(f"  First document: {details['first_doc']['doc_id']} ({details['first_doc']['statute_count']} statutes)", "INFO")
                for i, merged_doc in enumerate(details["merged_docs"], 1):
                    self.log_message(f"  Merged document {i}: {merged_doc['doc_id']} ({merged_doc['statute_count']} statutes)", "INFO")
                    # Show statute details for merged documents
                    for j, (name, date, type_) in enumerate(zip(merged_doc['statute_names'], merged_doc['statute_dates'], merged_doc['statute_types'])):
                        self.log_message(f"    - {name} ({date}, {type_})", "INFO")
                self.log_message("", "INFO")
        
        self.log_message("=" * 60, "INFO")
    
    def group_statutes_from_database(self) -> Dict[str, List[Dict]]:
        """Group statutes from database using base_name field (fallback)"""
        try:
            self.log_message("Loading statutes from old database structure...")
            statutes = list(self.source_col.find({}))
            
            groupings = defaultdict(list)
            for statute in statutes:
                if self.stop_processing:
                    break
                    
                base_name = statute.get("base_name", statute.get("Statute_Name", ""))
                if base_name:
                    groupings[base_name].append(statute)
            
            self.log_message(f"Grouped {len(statutes)} statutes into {len(groupings)} groups")
            return dict(groupings)
            
        except Exception as e:
            self.log_message(f"Error grouping statutes: {str(e)}", "ERROR")
            return {}
    
    def parse_date_vectorized(self, date_strings: np.ndarray) -> np.ndarray:
        """Parse date strings using NumPy vectorized operations"""
        if not date_strings.size:
            return np.array([])
        
        def parse_single_date(date_str):
            if not date_str or pd.isna(date_str):
                return None
            try:
                # First format the date to DD-MMM-YYYY format
                formatted_date = format_date_to_dd_mmm_yyyy(str(date_str))
                if not formatted_date:
                    return None
                # Then parse the formatted date
                return parser.parse(formatted_date, fuzzy=True)
            except (ValueError, TypeError):
                self.metadata["processing_details"]["date_parsing_errors"] += 1
                return None
        
        parsed_dates = np.vectorize(parse_single_date, otypes=[object])(date_strings)
        return parsed_dates
    
    def get_version_label_vectorized(self, indices: np.ndarray, total_counts: np.ndarray) -> np.ndarray:
        """Generate version labels using NumPy vectorized operations"""
        def get_single_label(index, total):
            if index == 0:
                return "Original"
            elif index == 1:
                return "First Amendment"
            elif index == 2:
                return "Second Amendment"
            elif index == 3:
                return "Third Amendment"
            elif index == 4:
                return "Fourth Amendment"
            elif index == 5:
                return "Fifth Amendment"
            else:
                return f"{index + 1}th Amendment"
        
        return np.vectorize(get_single_label)(indices, total_counts)
    
    def ask_gpt_for_version_order(self, statute_a: Dict, statute_b: Dict, group_name: str = "") -> Dict:
        """Use GPT to decide which statute came first if dates are identical or missing"""
        if not self.client_aoai or not self.use_gpt_var.get():
            return {'order': 'A', 'reason': 'GPT not available or disabled'}
        
        cache_key = f"version_order:{statute_a.get('_id')}:{statute_b.get('_id')}"
        
        if self.cache_gpt_var.get():
            cached_result = gpt_cache.get(cache_key)
            if cached_result:
                self.metadata["gpt_usage"]["gpt_cache_hits"] += 1
                return cached_result
        
        try:
            system_prompt = """You are a legal expert analyzing Pakistani statutes. Given two statutes with identical or missing dates, determine which one came first based on:
1. Legal hierarchy (Act > Ordinance > Law > Rule > Regulation)
2. Amendment sequence (Original > First Amendment > Second Amendment)
3. Content analysis and context clues
4. Legal terminology and language evolution

Respond with 'A' or 'B' and a brief reason."""
            
            user_prompt = f"""
Group: {group_name}

Statute A: {statute_a.get('Statute_Name', '')}
- Date: {statute_a.get('Date', 'No date')}
- Type: {statute_a.get('Statute_Type', 'Unknown')}
- Province: {statute_a.get('Province', 'Unknown')}

Statute B: {statute_b.get('Statute_Name', '')}
- Date: {statute_b.get('Date', 'No date')}
- Type: {statute_b.get('Statute_Type', 'Unknown')}
- Province: {statute_b.get('Province', 'Unknown')}

Which statute came first? Respond with 'A' or 'B' and explain why.
"""
            
            response = self.client_aoai.chat.completions.create(
                model=self.gpt_model_var.get(),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                max_tokens=5000
            )
            
            content = response.choices[0].message.content.strip()
            
            if content.upper().startswith('A'):
                result = {'order': 'A', 'reason': content}
            elif content.upper().startswith('B'):
                result = {'order': 'B', 'reason': content}
            else:
                result = {'order': 'A', 'reason': f'GPT response unclear: {content}'}
            
            if self.cache_gpt_var.get():
                gpt_cache.set(cache_key, result)
            
            self.metadata["gpt_usage"]["gpt_calls_made"] += 1
            return result
            
        except Exception as e:
            self.metadata["gpt_usage"]["gpt_errors"] += 1
            self.log_message(f"GPT error: {str(e)}", "WARNING")
            return {'order': 'A', 'reason': f'GPT error: {str(e)}'}
    
    def assign_version_labels_vectorized(self, groupings: Dict[str, List[Dict]]) -> Dict[str, List[Dict]]:
        """Assign version labels to statutes within each base group using NumPy optimization"""
        versioned_groupings = {}
        self.metadata["total_groups_processed"] = len(groupings)
        
        processed_groups = 0
        total_input_statutes = sum(len(statutes) for statutes in groupings.values())
        self.log_message(f"Starting versioning process with {len(groupings)} groups and {total_input_statutes} total statutes", "DEBUG")
        
        for base_name, statutes in groupings.items():
            if self.stop_processing:
                break
                
            if not statutes:
                self.log_message(f"Group '{base_name}': Skipping empty group", "DEBUG")
                continue
            
            original_count = len(statutes)
            self.log_message(f"Group '{base_name}': Processing {original_count} statutes", "DEBUG")
            
            processed_groups += 1
            progress_percent = (processed_groups / len(groupings)) * 70  # 70% of total progress
            self.progress_queue.put({
                'type': 'progress', 
                'value': 10 + progress_percent, 
                'message': f'Processing group {processed_groups}/{len(groupings)}: {base_name}'
            })
            
            self.metadata["total_statutes_versioned"] += len(statutes)
            
            if len(statutes) == 1:
                statutes[0]["Version_Label"] = "Original"
                versioned_groupings[base_name] = statutes
                self.metadata["versioning_stats"]["groups_with_single_version"] += 1
                self.metadata["version_label_distribution"]["version_labels"]["Original"] += 1
                self.log_message(f"Group '{base_name}': Single statute assigned 'Original' label", "DEBUG")
            else:
                # Sort by date and resolve ambiguous ordering
                self.log_message(f"Group '{base_name}': Sorting {len(statutes)} statutes by date", "DEBUG")
                sorted_statutes = self.sort_statutes_by_date_vectorized(statutes)
                self.log_message(f"Group '{base_name}': After sorting: {len(sorted_statutes)} statutes", "DEBUG")
                
                sorted_statutes = self.resolve_ambiguous_ordering_vectorized(sorted_statutes, base_name)
                self.log_message(f"Group '{base_name}': After ambiguous resolution: {len(sorted_statutes)} statutes", "DEBUG")
                
                # Assign version labels
                indices = np.arange(len(sorted_statutes))
                total_count = np.full(len(sorted_statutes), len(sorted_statutes))
                version_labels = self.get_version_label_vectorized(indices, total_count)
                
                for statute, label in zip(sorted_statutes, version_labels):
                    statute["Version_Label"] = label
                    self.metadata["version_label_distribution"]["version_labels"][label] += 1
                
                versioned_groupings[base_name] = sorted_statutes
                self.metadata["versioning_stats"]["groups_with_multiple_versions"] += 1
                self.log_message(f"Group '{base_name}': Final versioned count: {len(sorted_statutes)} statutes", "DEBUG")
            
            # Update real-time stats
            self.progress_queue.put({'type': 'stats', 'stats': self.metadata})
        
        # Calculate final statistics
        if versioned_groupings:
            version_counts = np.array([len(statutes) for statutes in versioned_groupings.values()])
            self.metadata["versioning_stats"]["max_versions_in_group"] = int(np.max(version_counts))
            self.metadata["versioning_stats"]["average_versions_per_group"] = float(np.mean(version_counts))
            self.metadata["versioning_stats"]["total_versions_created"] = int(np.sum(version_counts))
        
        total_output_statutes = sum(len(statutes) for statutes in versioned_groupings.values())
        self.log_message(f"Versioning complete: {len(versioned_groupings)} groups, {total_output_statutes} total statutes (input: {total_input_statutes})", "DEBUG")
        
        if total_input_statutes != total_output_statutes:
            self.log_message(f"WARNING: Statute count mismatch! Input: {total_input_statutes}, Output: {total_output_statutes}", "WARNING")
        
        # Log versioning summary
        self.log_message("=" * 60, "INFO")
        self.log_message("VERSIONING PROCESS SUMMARY", "INFO")
        self.log_message("=" * 60, "INFO")
        self.log_message(f"Total groups processed: {len(versioned_groupings)}", "INFO")
        self.log_message(f"Total statutes versioned: {total_output_statutes}", "INFO")
        self.log_message(f"Groups with single version: {self.metadata['versioning_stats']['groups_with_single_version']}", "INFO")
        self.log_message(f"Groups with multiple versions: {self.metadata['versioning_stats']['groups_with_multiple_versions']}", "INFO")
        self.log_message(f"Max versions in group: {self.metadata['versioning_stats']['max_versions_in_group']}", "INFO")
        self.log_message(f"Average versions per group: {self.metadata['versioning_stats']['average_versions_per_group']:.2f}", "INFO")
        self.log_message("=" * 60, "INFO")
        
        return versioned_groupings
    
    def sort_statutes_by_date_vectorized(self, statutes: List[Dict]) -> List[Dict]:
        """Sort statutes by date chronologically using NumPy"""
        if not statutes:
            return []
        
        original_count = len(statutes)
        self.log_message(f"Sorting {original_count} statutes by date", "DEBUG")
        
        date_strings = np.array([statute.get("Date", "") for statute in statutes])
        parsed_dates = self.parse_date_vectorized(date_strings)
        
        # Create sort keys
        sort_keys = np.where(parsed_dates != None, parsed_dates, np.datetime64('9999-12-31'))
        sorted_indices = np.argsort(sort_keys)
        
        sorted_statutes = [statutes[i] for i in sorted_indices]
        
        if len(sorted_statutes) != original_count:
            self.log_message(f"WARNING: Statute count changed during sorting! Original: {original_count}, After sorting: {len(sorted_statutes)}", "WARNING")
        else:
            self.log_message(f"Sorting complete: {len(sorted_statutes)} statutes", "DEBUG")
        
        return sorted_statutes
    
    def resolve_ambiguous_ordering_vectorized(self, statutes: List[Dict], group_name: str = "") -> List[Dict]:
        """Resolve ambiguous ordering using GPT when dates are identical or missing"""
        if len(statutes) < 2 or not self.use_gpt_var.get():
            self.log_message(f"Group '{group_name}': Skipping ambiguous resolution (statutes: {len(statutes)}, GPT enabled: {self.use_gpt_var.get()})", "DEBUG")
            return statutes
        
        original_count = len(statutes)
        self.log_message(f"Group '{group_name}': Resolving ambiguous ordering for {original_count} statutes", "DEBUG")
        
        # Work with a copy of the statutes list to avoid numpy array issues with dictionaries
        result_statutes = statutes.copy()
        date_strings = np.array([s.get("Date", "") for s in result_statutes])
        parsed_dates = self.parse_date_vectorized(date_strings)
        
        # Find pairs with identical or missing dates
        ambiguous_pairs = []
        for i in range(len(result_statutes) - 1):
            date1 = parsed_dates[i]
            date2 = parsed_dates[i + 1]
            
            if (date1 == date2) or (date1 is None and date2 is None):
                ambiguous_pairs.append((i, i + 1))
        
        self.log_message(f"Group '{group_name}': Found {len(ambiguous_pairs)} ambiguous pairs", "DEBUG")
        
        # Resolve ambiguous pairs using GPT
        for i, j in ambiguous_pairs:
            if self.stop_processing:
                break
                
            if i < len(result_statutes) and j < len(result_statutes):
                gpt_result = self.ask_gpt_for_version_order(
                    result_statutes[i], 
                    result_statutes[j], 
                    group_name
                )
                
                self.metadata["gpt_usage"]["gpt_ordering_decisions"].append({
                    'group': group_name,
                    'statute_a': result_statutes[i].get('Statute_Name', ''),
                    'statute_b': result_statutes[j].get('Statute_Name', ''),
                    'gpt_order': gpt_result['order'],
                    'gpt_reason': gpt_result['reason']
                })
                
                if gpt_result['order'] == 'B':
                    # Swap the statutes directly in the list
                    result_statutes[i], result_statutes[j] = result_statutes[j], result_statutes[i]
                    # Update the parsed dates array to match
                    parsed_dates[i], parsed_dates[j] = parsed_dates[j], parsed_dates[i]
        
        if len(result_statutes) != original_count:
            self.log_message(f"WARNING: Statute count changed during ambiguous resolution! Original: {original_count}, After resolution: {len(result_statutes)}", "WARNING")
        else:
            self.log_message(f"Group '{group_name}': Ambiguous resolution complete: {len(result_statutes)} statutes", "DEBUG")
        
        return result_statutes
    
    def create_versioned_database_vectorized(self, versioned_groupings: Dict[str, List[Dict]]) -> int:
        """Create a new database with versioned structure"""
        self.target_col.delete_many({})
        self.log_message("Cleared target collection")
        
        created_count = 0
        total_input_statutes = sum(len(statutes) for statutes in versioned_groupings.values())
        total_output_versions = 0
        
        self.log_message(f"Creating versioned database with {len(versioned_groupings)} groups and {total_input_statutes} total statutes", "DEBUG")
        
        for base_name, statutes in versioned_groupings.items():
            if self.stop_processing:
                break
                
            original_statute_count = len(statutes)
            self.log_message(f"Group '{base_name}': Creating versioned document with {original_statute_count} statutes", "DEBUG")
            
            group_doc = {
                "base_name": base_name,
                "group_id": f"versioned_group_{base_name.lower().replace(' ', '_').replace('-', '_')}",
                "total_versions": len(statutes),
                "versions": []
            }
            
            for statute in statutes:
                version_doc = {
                    "version_label": statute.get("Version_Label", ""),
                    "statute_name": statute.get("Statute_Name", ""),
                    "date": statute.get("Date", ""),
                    "statute_type": statute.get("Statute_Type", ""),
                    "province": statute.get("Province", ""),
                    "year": statute.get("Year", ""),
                    "base_name": statute.get("base_name", ""),
                    "sections": statute.get("Sections", []),
                    "original_id": str(statute.get("_id", "")),
                    "act_ordinance": statute.get("Act_Ordinance"),
                    "citations": statute.get("Citations"),
                    "metadata": {
                        k: v for k, v in statute.items() 
                        if k not in ["_id", "Statute_Name", "Date", "Statute_Type", "Sections", "base_name", 
                                    "Act_Ordinance", "Citations", "Province", "Year", "Version_Label"]
                    }
                }
                group_doc["versions"].append(version_doc)
            
            final_version_count = len(group_doc["versions"])
            if final_version_count != original_statute_count:
                self.log_message(f"WARNING: Group '{base_name}': Version count mismatch! Original statutes: {original_statute_count}, Final versions: {final_version_count}", "WARNING")
            
            try:
                self.target_col.insert_one(group_doc)
                created_count += 1
                total_output_versions += final_version_count
                self.metadata["processing_details"]["groups_created"] += 1
                self.log_message(f"Group '{base_name}': Successfully created with {final_version_count} versions", "DEBUG")
            except Exception as e:
                self.log_message(f"Error creating versioned group for {base_name}: {e}", "ERROR")
        
        self.metadata["processing_details"]["database_updates"] = created_count
        
        if total_input_statutes != total_output_versions:
            self.log_message(f"WARNING: Database creation mismatch! Input statutes: {total_input_statutes}, Output versions: {total_output_versions}", "WARNING")
        else:
            self.log_message(f"Database creation complete: {created_count} groups, {total_output_versions} versions", "DEBUG")
        
        return created_count
    
    def save_versioning_info(self, versioned_groupings: Dict[str, List[Dict]]):
        """Save versioning information to JSON file"""
        try:
            json_data = {}
            for base_name, statutes in versioned_groupings.items():
                json_data[base_name] = []
                for statute in statutes:
                    statute_copy = {
                        "id": str(statute["_id"]),
                        "Statute_Name": statute.get("Statute_Name", ""),
                        "Date": statute.get("Date", ""),
                        "Version_Label": statute.get("Version_Label", ""),
                        "base_name": statute.get("base_name", "")
                    }
                    json_data[base_name].append(statute_copy)
            
            # Create directory if it doesn't exist
            os.makedirs("05_statute_versioning", exist_ok=True)
            
            versioning_filename = f"versioned_statutes_{self.target_db_var.get()}_{self.target_collection_var.get()}_{date.today().isoformat()}.json"
            versioning_path = f"05_statute_versioning/{versioning_filename}"
            
            with open(versioning_path, "w", encoding="utf-8") as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)
            
            self.log_message(f"Versioning info saved to: {versioning_path}")
            
        except Exception as e:
            self.log_message(f"Error saving versioning info: {str(e)}", "ERROR")
    
    def preview_groups(self):
        """Preview groups before processing"""
        if self.client_mongo is None or self.source_col is None:
            messagebox.showerror("Error", "Please test database connection first!")
            return
        
        try:
            # Load a sample of groups
            groupings = self.load_groupings_from_database()
            if not groupings:
                groupings = self.group_statutes_from_database()
            
            if not groupings:
                messagebox.showwarning("Warning", "No groups found to preview!")
                return
            
            # Create preview window
            preview_window = tk.Toplevel(self.root)
            preview_window.title("Groups Preview")
            preview_window.geometry("800x600")
            
            # Create treeview for preview
            columns = ("Group Name", "Statute Count", "Sample Statute")
            preview_tree = ttk.Treeview(preview_window, columns=columns, show="headings")
            
            for col in columns:
                preview_tree.heading(col, text=col)
                preview_tree.column(col, width=250)
            
            scrollbar_preview = ttk.Scrollbar(preview_window, orient=tk.VERTICAL, command=preview_tree.yview)
            preview_tree.configure(yscrollcommand=scrollbar_preview.set)
            
            # Populate preview data
            for base_name, statutes in list(groupings.items())[:100]:  # Show first 100 groups
                sample_statute = statutes[0].get('Statute_Name', 'Unknown') if statutes else 'No statutes'
                preview_tree.insert("", "end", values=(base_name, len(statutes), sample_statute))
            
            preview_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar_preview.pack(side=tk.RIGHT, fill=tk.Y)
            
            # Add summary label
            summary_label = ttk.Label(preview_window, text=f"Total Groups: {len(groupings)} (showing first 100)")
            summary_label.pack(side=tk.BOTTOM, pady=10)
            
        except Exception as e:
            messagebox.showerror("Preview Error", f"Failed to preview groups:\n{str(e)}")
    
    def export_results(self):
        """Export processing results"""
        filename = filedialog.asksaveasfilename(
            title="Export Results",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                export_data = {
                    "metadata": self.metadata,
                    "timestamp": datetime.now().isoformat(),
                    "configuration": {
                        "source_db": self.source_db_var.get(),
                        "source_collection": self.source_collection_var.get(),
                        "target_db": self.target_db_var.get(),
                        "target_collection": self.target_collection_var.get(),
                        "enable_gpt_ordering": self.use_gpt_var.get(),
                        "enable_vectorized_processing": self.vectorized_var.get(),
                        "batch_size": self.batch_size_var.get()
                    }
                }
                
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, ensure_ascii=False, indent=2)
                
                self.log_message(f"Results exported to {filename}")
                messagebox.showinfo("Success", "Results exported successfully!")
                
            except Exception as e:
                self.log_message(f"Export failed: {str(e)}", "ERROR")
                messagebox.showerror("Export Error", f"Failed to export results:\n{str(e)}")
    
    def refresh_statistics(self):
        """Refresh statistics display - showing only summary data"""
        try:
            self.stats_text.delete(1.0, tk.END)
            
            stats_text = "SUMMARY STATISTICS\n"
            stats_text += "=" * 30 + "\n\n"
            
            # Add source statistics summary if available
            if hasattr(self, 'source_stats') and self.source_stats:
                stats_text += "📊 SOURCE COLLECTION:\n"
                stats_text += f"   - Collection: {self.source_stats.get('source_collection', 'Unknown')}\n"
                stats_text += f"   - Total groups: {self.source_stats.get('total_groups', 0)}\n"
                stats_text += f"   - Total statutes: {self.source_stats.get('total_statutes', 0)}\n"
                stats_text += f"   - Documents merged: {self.source_stats.get('documents_merged', 0)}\n\n"
            
            stats_text += "📊 TARGET COLLECTION:\n"
            stats_text += f"   - Groups processed: {self.metadata['total_groups_processed']}\n"
            stats_text += f"   - Statutes versioned: {self.metadata['total_statutes_versioned']}\n"
            stats_text += f"   - Groups created: {self.metadata['processing_details']['groups_created']}\n\n"
            
            # Summary versioning stats
            versioning_stats = self.metadata['versioning_stats']
            stats_text += "📊 VERSIONING SUMMARY:\n"
            stats_text += f"   - Single version groups: {versioning_stats['groups_with_single_version']}\n"
            stats_text += f"   - Multiple version groups: {versioning_stats['groups_with_multiple_versions']}\n"
            stats_text += f"   - Max versions per group: {versioning_stats['max_versions_in_group']}\n"
            stats_text += f"   - Average versions per group: {versioning_stats['average_versions_per_group']:.2f}\n\n"
            
            # Summary processing stats
            processing_details = self.metadata['processing_details']
            stats_text += "📊 PROCESSING SUMMARY:\n"
            stats_text += f"   - Valid dates: {processing_details['statutes_with_valid_dates']}\n"
            stats_text += f"   - Invalid dates: {processing_details['statutes_with_invalid_dates']}\n"
            stats_text += f"   - Missing dates: {processing_details['statutes_with_missing_dates']}\n\n"
            
            # Summary GPT stats
            gpt_usage = self.metadata['gpt_usage']
            stats_text += "📊 GPT USAGE SUMMARY:\n"
            stats_text += f"   - Calls made: {gpt_usage['gpt_calls_made']}\n"
            stats_text += f"   - Cache hits: {gpt_usage['gpt_cache_hits']}\n"
            stats_text += f"   - Errors: {gpt_usage['gpt_errors']}\n\n"
            
            # Note about detailed logs
            stats_text += "📋 NOTE: Detailed processing, merging, and versioning information is available in the Logs tab.\n"
            stats_text += "   Set log level to 'DEBUG' to see comprehensive details.\n"
            
            self.stats_text.insert(1.0, stats_text)
            
        except Exception as e:
            self.log_message(f"Error refreshing statistics: {str(e)}", "ERROR")
    
    def export_statistics(self):
        """Export statistics to file"""
        filename = filedialog.asksaveasfilename(
            title="Export Statistics",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                if filename.endswith('.json'):
                    with open(filename, 'w', encoding='utf-8') as f:
                        json.dump(self.metadata, f, ensure_ascii=False, indent=2)
                else:
                    with open(filename, 'w', encoding='utf-8') as f:
                        stats_content = self.stats_text.get(1.0, tk.END)
                        f.write(stats_content)
                
                self.log_message(f"Statistics exported to {filename}")
                messagebox.showinfo("Success", "Statistics exported successfully!")
                
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export statistics:\n{str(e)}")
    
    def clear_statistics(self):
        """Clear statistics display"""
        self.stats_text.delete(1.0, tk.END)
    
    def clear_logs(self):
        """Clear log display"""
        self.log_text.delete(1.0, tk.END)
    
    def save_logs(self):
        """Save logs to file"""
        filename = filedialog.asksaveasfilename(
            title="Save Logs",
            defaultextension=".log",
            filetypes=[("Log files", "*.log"), ("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    log_content = self.log_text.get(1.0, tk.END)
                    f.write(log_content)
                
                messagebox.showinfo("Success", "Logs saved successfully!")
                
            except Exception as e:
                messagebox.showerror("Save Error", f"Failed to save logs:\n{str(e)}")
    
    def load_collections_for_comparison(self):
        """Load data from both source and target collections for comparison"""
        try:
            # Ensure comparison_data is properly initialized
            if not hasattr(self, 'comparison_data'):
                self.comparison_data = {
                    'merge_details': {},
                    'group_details': {},
                    'source_data': {},
                    'target_data': {},
                    'comparison_results': {},
                    'approved_groups': set()
                }
            
            self.log_message("Loading collections for comparison...")
            self.update_status("Loading collections...")
            
            # Connect to MongoDB
            if self.client_mongo is None:
                self.client_mongo = MongoClient(self.mongo_uri_var.get())
            
            # Get database and collection names
            source_db_name = self.source_db_var.get()
            source_collection_name = self.source_collection_var.get()
            target_db_name = self.target_db_var.get()
            target_collection_name = self.target_collection_var.get()
            
            # Load source collection data
            source_db = self.client_mongo[source_db_name]
            source_col = source_db[source_collection_name]
            
            source_data = {}
            source_count = 0
            for doc in source_col.find():
                source_count += 1
                if 'base_name' in doc:  # Source collection uses 'base_name' field
                    group_name = doc['base_name']
                    if group_name not in source_data:
                        source_data[group_name] = []
                    source_data[group_name].append(doc)
                else:
                    self.log_message(f"Document missing 'base_name' field: {list(doc.keys())}", "DEBUG")
            
            # Load target data - either from pending data or from target collection
            target_data = {}
            target_count = 0
            
            if hasattr(self, 'pending_versioned_data') and self.pending_versioned_data is not None and self.pending_versioned_data:
                # Use pending versioned data instead of loading from target collection
                self.log_message("Using pending versioned data for comparison")
                for base_name, statutes in self.pending_versioned_data.items():
                    target_count += 1
                    # Convert statutes to the same format as stored in database
                    versioned_statutes = []
                    for statute in statutes:
                        # Format the date to DD-MMM-YYYY format and convert to lowercase field
                        raw_date = statute.get("Date", "")
                        formatted_date = format_date_to_dd_mmm_yyyy(raw_date) if raw_date else ""
                        
                        versioned_statute = {
                            "version_label": statute.get("Version_Label", ""),
                            "statute_name": statute.get("Statute_Name", ""),
                            "date": formatted_date,  # Convert Date to date and format it
                            "statute_type": statute.get("Statute_Type", ""),
                            "province": statute.get("Province", ""),
                            "year": statute.get("Year", ""),
                            "base_name": statute.get("base_name", ""),
                            "sections": statute.get("Sections", []),
                            "original_id": str(statute.get("_id", "")),
                            "act_ordinance": statute.get("Act_Ordinance"),
                            "citations": statute.get("Citations"),
                            "metadata": {
                                k: v for k, v in statute.items() 
                                if k not in ["_id", "Statute_Name", "Date", "Statute_Type", "Sections", "base_name", 
                                            "Act_Ordinance", "Citations", "Province", "Year", "Version_Label"]
                            }
                        }
                        versioned_statutes.append(versioned_statute)
                    
                    # Create a mock document structure for comparison
                    mock_doc = {
                        'base_name': base_name,
                        'versions': versioned_statutes  # These are now properly formatted version documents
                    }
                    target_data[base_name] = [mock_doc]
            else:
                # Load from target collection (fallback)
                target_db = self.client_mongo[target_db_name]
                target_col = target_db[target_collection_name]
                
                for doc in target_col.find():
                    target_count += 1
                    if 'base_name' in doc:  # Target collection also uses 'base_name' field
                        group_name = doc['base_name']
                        if group_name not in target_data:
                            target_data[group_name] = []
                        target_data[group_name].append(doc)
                    else:
                        self.log_message(f"Target document missing 'base_name' field: {list(doc.keys())}", "DEBUG")
            
            # Store data
            self.comparison_data['source_data'] = source_data
            self.comparison_data['target_data'] = target_data
            
            # Update summary
            summary = f"Collections loaded successfully!\n"
            summary += f"Source ({source_db_name}.{source_collection_name}): {len(source_data)} groups, {source_count} total documents\n"
            
            if hasattr(self, 'pending_versioned_data'):
                summary += f"Target (Pending Data): {len(target_data)} groups, {target_count} total documents\n"
                summary += f"Status: Ready for approval\n"
            else:
                summary += f"Target ({target_db_name}.{target_collection_name}): {len(target_data)} groups, {target_count} total documents\n"
            
            # Add debug info
            if source_count > 0 and len(source_data) == 0:
                self.log_message(f"WARNING: Found {source_count} source documents but 0 groups. Checking document structure...", "WARNING")
                sample_doc = list(source_col.find().limit(1))
                if sample_doc:
                    self.log_message(f"Sample source document keys: {list(sample_doc[0].keys())}", "DEBUG")
            
            if target_count > 0 and len(target_data) == 0:
                self.log_message(f"WARNING: Found {target_count} target documents but 0 groups. Checking document structure...", "WARNING")
                if not hasattr(self, 'pending_versioned_data'):
                    sample_doc = list(target_col.find().limit(1))
                    if sample_doc:
                        self.log_message(f"Sample target document keys: {list(sample_doc[0].keys())}", "DEBUG")
            
            self.summary_text.delete(1.0, tk.END)
            self.summary_text.insert(tk.END, summary)
            
            self.log_message(f"Loaded {len(source_data)} source groups and {len(target_data)} target groups")
            self.update_status("Collections loaded successfully")
            
        except Exception as e:
            error_msg = f"Error loading collections: {str(e)}"
            self.log_message(error_msg, "ERROR")
            self.update_status("Error loading collections")
            messagebox.showerror("Error", error_msg)
    
    def compare_collections(self):
        """Compare the loaded collections and display differences"""
        try:
            # Ensure comparison_data is properly initialized
            if not hasattr(self, 'comparison_data'):
                self.comparison_data = {
                    'merge_details': {},
                    'group_details': {},
                    'source_data': {},
                    'target_data': {},
                    'comparison_results': {},
                    'approved_groups': set()
                }
            
            if not self.comparison_data.get('source_data') or not self.comparison_data.get('target_data'):
                messagebox.showwarning("Warning", "Please load collections first")
                return
            
            self.log_message("Comparing collections...")
            self.update_status("Comparing collections...")
            
            source_data = self.comparison_data['source_data']
            target_data = self.comparison_data['target_data']
            
            # Clear existing tree data
            for tree in [self.source_tree, self.target_tree]:
                for item in tree.get_children():
                    tree.delete(item)
            
            # Get all unique group names
            all_groups = set(source_data.keys()) | set(target_data.keys())
            
            # Debug logging
            self.log_message(f"Comparing {len(all_groups)} groups", "DEBUG")
            self.log_message(f"Source data keys: {list(source_data.keys())[:5]}", "DEBUG")
            self.log_message(f"Target data keys: {list(target_data.keys())[:5]}", "DEBUG")
            
            # Compare and populate trees
            comparison_results = {
                'only_in_source': [],
                'only_in_target': [],
                'in_both': [],
                'different_counts': []
            }
            
            for group_name in sorted(all_groups):
                source_group = source_data.get(group_name, [])
                target_group = target_data.get(group_name, [])
                
                # Count statutes in source group
                source_count = 0
                source_statutes = []
                for doc in source_group:
                    if 'statutes' in doc:
                        source_count += len(doc['statutes'])
                        source_statutes.extend(doc['statutes'])
                    else:
                        source_count += 1  # Fallback: count the document itself
                        source_statutes.append(doc)
                
                # Count versions in target group
                target_count = 0
                target_versions = []
                for doc in target_group:
                    if 'versions' in doc:
                        target_count += len(doc['versions'])
                        target_versions.extend(doc['versions'])
                    else:
                        target_count += 1  # Fallback: count the document itself
                        target_versions.append(doc)
                
                # Ensure target_versions is a list
                if not isinstance(target_versions, list):
                    target_versions = [target_versions]
                
                # Store detailed information
                try:
                    # Ensure group_details exists
                    if 'group_details' not in self.comparison_data:
                        self.comparison_data['group_details'] = {}
                    
                    self.comparison_data['group_details'][group_name] = {
                        'source_statutes': source_statutes,
                        'target_versions': target_versions,
                        'source_count': source_count,
                        'target_count': target_count
                    }
                except Exception as e:
                    self.log_message(f"Error storing group details for '{group_name}': {str(e)}", "ERROR")
                
                # Determine status
                if group_name in source_data and group_name in target_data:
                    if source_count == target_count:
                        status = "Same"
                        comparison_results['in_both'].append(group_name)
                    else:
                        status = f"Different ({source_count} vs {target_count})"
                        comparison_results['different_counts'].append(group_name)
                        # Log detailed information about count differences
                        self.log_message(f"Count difference detected: Group '{group_name}' - Source: {source_count} statutes, Target: {target_count} versions", "WARNING")
                elif group_name in source_data:
                    status = "Only in Source"
                    comparison_results['only_in_source'].append(group_name)
                else:
                    status = "Only in Target"
                    comparison_results['only_in_target'].append(group_name)
                
                # Add to source tree with expandable structure
                if group_name in source_data:
                    source_item = self.source_tree.insert('', tk.END, values=(
                        group_name, 
                        source_count, 
                        status
                    ), tags=('group',))
                    
                    # Add individual statutes as children
                    for i, statute in enumerate(source_statutes[:10]):  # Limit to first 10 for performance
                        statute_name = statute.get('Statute_Name', f'Statute {i+1}')
                        statute_date = statute.get('Date', 'No date')
                        self.source_tree.insert(source_item, tk.END, values=(
                            f"  {statute_name}",
                            f"Date: {statute_date}",
                            ""
                        ), tags=('statute',))
                    
                    if len(source_statutes) > 10:
                        self.source_tree.insert(source_item, tk.END, values=(
                            f"  ... and {len(source_statutes) - 10} more statutes",
                            "",
                            ""
                        ), tags=('more',))
                
                # Add to target tree with expandable structure and selection
                if group_name in target_data:
                    target_item = self.target_tree.insert('', tk.END, values=(
                        "☐",  # Selection checkbox
                        group_name, 
                        target_count, 
                        f"{target_count} versions",
                        status
                    ), tags=('group',))
                    
                    # Add individual versions as children
                    for i, version in enumerate(target_versions[:10]):  # Limit to first 10 for performance
                        version_label = version.get('version_label', f'Version {i+1}')
                        statute_name = version.get('statute_name', f'Statute {i+1}')
                        version_date = version.get('date', 'No date')
                        self.target_tree.insert(target_item, tk.END, values=(
                            "",
                            f"  {version_label}: {statute_name}",
                            f"Date: {version_date}",
                            "",
                            ""
                        ), tags=('version',))
                    
                    if len(target_versions) > 10:
                        self.target_tree.insert(target_item, tk.END, values=(
                            "",
                            f"  ... and {len(target_versions) - 10} more versions",
                            "",
                            "",
                            ""
                        ), tags=('more',))
            
            # Update summary
            summary = f"Comparison Results:\n"
            summary += f"Groups in both collections: {len(comparison_results['in_both'])}\n"
            summary += f"Groups only in source: {len(comparison_results['only_in_source'])}\n"
            summary += f"Groups only in target: {len(comparison_results['only_in_target'])}\n"
            summary += f"Groups with different counts: {len(comparison_results['different_counts'])}\n\n"
            
            if comparison_results['only_in_source']:
                summary += f"Only in source: {', '.join(comparison_results['only_in_source'][:5])}"
                if len(comparison_results['only_in_source']) > 5:
                    summary += f" ... and {len(comparison_results['only_in_source']) - 5} more\n"
                summary += "\n"
            
            if comparison_results['only_in_target']:
                summary += f"Only in target: {', '.join(comparison_results['only_in_target'][:5])}"
                if len(comparison_results['only_in_target']) > 5:
                    summary += f" ... and {len(comparison_results['only_in_target']) - 5} more\n"
                summary += "\n"
            
            if comparison_results['different_counts']:
                summary += f"Different counts: {', '.join(comparison_results['different_counts'][:5])}"
                if len(comparison_results['different_counts']) > 5:
                    summary += f" ... and {len(comparison_results['different_counts']) - 5} more\n"
            
            self.summary_text.delete(1.0, tk.END)
            self.summary_text.insert(tk.END, summary)
            
            # Store comparison results
            self.comparison_data['comparison_results'] = comparison_results
            
            self.log_message(f"Comparison complete: {len(all_groups)} groups analyzed")
            self.update_status("Comparison complete")
            
        except Exception as e:
            error_msg = f"Error comparing collections: {str(e)}"
            self.log_message(error_msg, "ERROR")
            self.update_status("Error comparing collections")
            messagebox.showerror("Error", error_msg)
    
    def export_comparison(self):
        """Export comparison results to a file"""
        try:
            if not self.comparison_data['comparison_results']:
                messagebox.showwarning("Warning", "Please run comparison first")
                return
            
            # Ask user for file location
            filename = filedialog.asksaveasfilename(
                title="Export Comparison Results",
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("Text files", "*.txt"), ("All files", "*.*")]
            )
            
            if not filename:
                return
            
            # Prepare export data
            export_data = {
                'timestamp': datetime.now().isoformat(),
                'source_collection': f"{self.source_db_var.get()}.{self.source_collection_var.get()}",
                'target_collection': f"{self.target_db_var.get()}.{self.target_collection_var.get()}",
                'comparison_results': self.comparison_data['comparison_results'],
                'summary': self.summary_text.get(1.0, tk.END).strip()
            }
            
            # Export based on file extension
            if filename.lower().endswith('.json'):
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False)
            else:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write("Collection Comparison Report\n")
                    f.write("=" * 50 + "\n\n")
                    f.write(f"Generated: {export_data['timestamp']}\n")
                    f.write(f"Source: {export_data['source_collection']}\n")
                    f.write(f"Target: {export_data['target_collection']}\n\n")
                    f.write(export_data['summary'])
            
            self.log_message(f"Comparison exported to {filename}")
            self.update_status("Comparison exported")
            messagebox.showinfo("Success", f"Comparison results exported to {filename}")
            
        except Exception as e:
            error_msg = f"Error exporting comparison: {str(e)}"
            self.log_message(error_msg, "ERROR")
            messagebox.showerror("Error", error_msg)
    
    def clear_comparison(self):
        """Clear comparison data and display"""
        # Clear trees
        for tree in [self.source_tree, self.target_tree]:
            for item in tree.get_children():
                tree.delete(item)
        
        # Clear summary
        self.summary_text.delete(1.0, tk.END)
        
        # Clear comparison data
        self.comparison_data = {
            'source_data': {},
            'target_data': {},
            'comparison_results': {},
            'approved_groups': set(),
            'group_details': {}
        }
        
        self.log_message("Comparison data cleared")
        self.update_status("Comparison cleared")
    
    def toggle_group_selection(self, event):
        """Toggle selection of a group when double-clicked"""
        try:
            item = self.target_tree.selection()[0]
            group_name = self.target_tree.item(item, "values")[1]  # Group name is in second column
            
            if group_name in self.comparison_data['approved_groups']:
                self.comparison_data['approved_groups'].remove(group_name)
                self.target_tree.set(item, "Select", "☐")
                self.log_message(f"Unselected group: {group_name}")
            else:
                self.comparison_data['approved_groups'].add(group_name)
                self.target_tree.set(item, "Select", "☑")
                self.log_message(f"Selected group: {group_name}")
                
        except (IndexError, KeyError):
            pass
    
    def approve_selected_groups(self):
        """Approve only the currently selected groups"""
        try:
            selected_count = len(self.comparison_data['approved_groups'])
            self.log_message(f"Approved {selected_count} selected groups")
            
            # If we have pending data, create database with approved groups
            if hasattr(self, 'pending_versioned_data'):
                self.create_database_with_approved_groups()
            else:
                messagebox.showinfo("Approval", f"Approved {selected_count} groups for database insertion")
            
        except Exception as e:
            self.log_message(f"Error approving selected groups: {str(e)}", "ERROR")
    
    def approve_all_groups(self):
        """Approve all groups in the target collection"""
        try:
            if hasattr(self, 'pending_versioned_data'):
                # Approve all pending groups
                all_groups = set(self.pending_versioned_data.keys())
                self.comparison_data['approved_groups'] = all_groups
                
                # Update all checkboxes
                for item in self.target_tree.get_children():
                    group_name = self.target_tree.item(item, "values")[1]
                    if group_name in all_groups:
                        self.target_tree.set(item, "Select", "☑")
                
                self.log_message(f"Approved all {len(all_groups)} groups")
                self.create_database_with_approved_groups()
            else:
                # Fallback to existing behavior
                all_groups = set(self.comparison_data['target_data'].keys())
                self.comparison_data['approved_groups'] = all_groups
                
                # Update all checkboxes
                for item in self.target_tree.get_children():
                    group_name = self.target_tree.item(item, "values")[1]
                    if group_name in all_groups:
                        self.target_tree.set(item, "Select", "☑")
                
                self.log_message(f"Approved all {len(all_groups)} groups")
                messagebox.showinfo("Approval", f"Approved all {len(all_groups)} groups")
            
        except Exception as e:
            self.log_message(f"Error approving all groups: {str(e)}", "ERROR")
    
    def create_database_with_approved_groups(self):
        """Create database with approved groups from pending data"""
        try:
            if not hasattr(self, 'pending_versioned_data'):
                messagebox.showwarning("Warning", "No pending data available!")
                return
            
            if not self.comparison_data['approved_groups']:
                messagebox.showwarning("Warning", "No groups selected for approval!")
                return
            
            # Filter pending data to only include approved groups
            approved_groupings = {}
            for group_name in self.comparison_data['approved_groups']:
                if group_name in self.pending_versioned_data:
                    approved_groupings[group_name] = self.pending_versioned_data[group_name]
            
            if not approved_groupings:
                messagebox.showwarning("Warning", "No approved groups found in pending data!")
                return
            
            # Create database with approved groups
            created_count = self.create_database_after_approval(approved_groupings)
            
            # Clear pending data after successful creation
            delattr(self, 'pending_versioned_data')
            
            self.log_message(f"Successfully created database with {created_count} approved groups")
            messagebox.showinfo("Success", f"Database created successfully with {created_count} approved groups!")
            
        except Exception as e:
            error_msg = f"Error creating database with approved groups: {str(e)}"
            self.log_message(error_msg, "ERROR")
            messagebox.showerror("Error", error_msg)
    
    def reject_all_groups(self):
        """Reject all groups (clear selections)"""
        try:
            self.comparison_data['approved_groups'].clear()
            
            # Clear all checkboxes
            for item in self.target_tree.get_children():
                self.target_tree.set(item, "Select", "☐")
            
            self.log_message("Rejected all groups")
            messagebox.showinfo("Rejection", "Rejected all groups")
            
        except Exception as e:
            self.log_message(f"Error rejecting all groups: {str(e)}", "ERROR")
    
    def save_approved_to_database(self):
        """Save approved groups to a new approved collection in the database"""
        try:
            if not self.comparison_data['approved_groups']:
                messagebox.showwarning("Warning", "No groups selected for approval!")
                return
            
            # Get approved groups data
            approved_groups_data = []
            for group_name in self.comparison_data['approved_groups']:
                if group_name in self.comparison_data['target_data']:
                    group_docs = self.comparison_data['target_data'][group_name]
                    for doc in group_docs:
                        approved_groups_data.append(doc)
            
            if not approved_groups_data:
                messagebox.showwarning("Warning", "No approved group data found!")
                return
            
            # Create approved collection name
            source_collection = self.source_collection_var.get()
            approved_collection_name = f"{source_collection}_approved_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Connect to database
            if self.client_mongo is None:
                self.client_mongo = MongoClient(self.mongo_uri_var.get())
            
            target_db = self.client_mongo[self.target_db_var.get()]
            approved_collection = target_db[approved_collection_name]
            
            # Insert approved groups
            result = approved_collection.insert_many(approved_groups_data)
            
            self.log_message(f"Saved {len(result.inserted_ids)} approved documents to {approved_collection_name}")
            messagebox.showinfo("Success", f"Saved {len(result.inserted_ids)} approved documents to collection: {approved_collection_name}")
            
        except Exception as e:
            error_msg = f"Error saving approved groups to database: {str(e)}"
            self.log_message(error_msg, "ERROR")
            messagebox.showerror("Error", error_msg)
    
    def show_group_details(self, event):
        """Show detailed information about the selected group"""
        try:
            tree = event.widget
            selection = tree.selection()
            
            if not selection:
                return
            
            item = selection[0]
            values = tree.item(item, "values")
            
            # Get group name (different column positions for source vs target)
            if tree == self.source_tree:
                group_name = values[0]
            else:  # target_tree
                group_name = values[1]  # Group name is in second column
            
            # Check if this is a group item (not a child item)
            if not group_name.startswith("  "):
                if 'group_details' in self.comparison_data and group_name in self.comparison_data['group_details']:
                    details = self.comparison_data['group_details'][group_name]
                    
                    # Create detailed summary
                    detail_text = f"Group: {group_name}\n"
                    detail_text += f"Source Statutes: {details['source_count']}\n"
                    detail_text += f"Target Versions: {details['target_count']}\n\n"
                    
                    detail_text += "Source Statutes:\n"
                    for i, statute in enumerate(details['source_statutes'][:5]):
                        name = statute.get('Statute_Name', f'Statute {i+1}')
                        date = statute.get('Date', 'No date')
                        detail_text += f"  {i+1}. {name} ({date})\n"
                    
                    if len(details['source_statutes']) > 5:
                        detail_text += f"  ... and {len(details['source_statutes']) - 5} more\n"
                    
                    detail_text += "\nTarget Versions:\n"
                    for i, version in enumerate(details['target_versions'][:5]):
                        label = version.get('version_label', f'Version {i+1}')
                        name = version.get('statute_name', f'Statute {i+1}')
                        date = version.get('date', 'No date')
                        detail_text += f"  {i+1}. {label}: {name} ({date})\n"
                    
                    if len(details['target_versions']) > 5:
                        detail_text += f"  ... and {len(details['target_versions']) - 5} more\n"
                    
                    # Update summary text with details
                    self.summary_text.delete(1.0, tk.END)
                    self.summary_text.insert(tk.END, detail_text)
                    
        except Exception as e:
            self.log_message(f"Error showing group details: {str(e)}", "ERROR")
    
    def export_merge_details(self):
        """Export merge details to a JSON file"""
        try:
            if not self.comparison_data['merge_details']:
                messagebox.showwarning("Warning", "No merge details to export!")
                return
            
            # Ask user for file location
            filename = filedialog.asksaveasfilename(
                title="Export Merge Details",
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )
            
            if not filename:
                return
            
            # Prepare export data
            export_data = {
                'merge_details': self.comparison_data['merge_details']
            }
            
            # Export based on file extension
            if filename.lower().endswith('.json'):
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False)
            else:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            self.log_message(f"Merge details exported to {filename}")
            messagebox.showinfo("Success", "Merge details exported successfully!")
            
        except Exception as e:
            error_msg = f"Error exporting merge details: {str(e)}"
            self.log_message(error_msg, "ERROR")
            messagebox.showerror("Error", error_msg)
    
    def show_merge_summary(self):
        """Show a summary of merge details in a popup window"""
        try:
            if not self.comparison_data['merge_details']:
                messagebox.showwarning("Warning", "No merge details available!")
                return
            
            merge_details = self.comparison_data['merge_details']
            
            # Calculate summary statistics
            total_groups = len(merge_details)
            groups_with_merges = sum(1 for details in merge_details.values() if details["merged_docs"])
            total_merged_docs = sum(len(details["merged_docs"]) for details in merge_details.values())
            
            # Create summary text
            summary_text = f"""MERGE SUMMARY

Total Groups: {total_groups}
Groups with Merges: {groups_with_merges}
Total Documents Merged: {total_merged_docs}

MERGE LOGIC EXPLANATION:
=======================
1. Documents are grouped by 'base_name' field from source collection
2. Similar base_names (similarity >= 0.85) are merged together
3. Similarity is calculated using SequenceMatcher algorithm
4. Text normalization removes punctuation and converts to lowercase
5. Example: 'Benazir Bhutto Shaheed University At Layari Karachi'
   and 'Benazir Bhutto Shaheed University At Lyari Karachi'
   would be merged due to high similarity (only 'Layari' vs 'Lyari')

SIMILARITY CALCULATION:
======================
- Uses difflib.SequenceMatcher for string similarity
- Normalizes text by removing punctuation and converting to lowercase
- Returns a value between 0.0 (no similarity) and 1.0 (identical)
- Threshold of 0.85 means 85% similarity required for merging

DATE FORMATTING:
===============
- All dates are standardized to DD-MMM-YYYY format
- Handles various input formats (YYYY-MM-DD, DD/MM/YYYY, etc.)
- Missing dates are stored as empty strings

GROUPS WITH MERGES:
==================
"""
            
            # Add details for groups that had merges
            for base_name, details in merge_details.items():
                if details["merged_docs"]:
                    summary_text += f"\n{base_name}:\n"
                    summary_text += f"  First document: {details['first_doc']['doc_id']} ({details['first_doc']['statute_count']} statutes)\n"
                    for i, merged_doc in enumerate(details["merged_docs"], 1):
                        summary_text += f"  + Merged document {i}: {merged_doc['doc_id']} ({merged_doc['statute_count']} statutes)\n"
                        # Show statute details for merged documents
                        for j, (name, date, type_) in enumerate(zip(merged_doc['statute_names'], merged_doc['statute_dates'], merged_doc['statute_types'])):
                            summary_text += f"    - {name} ({date}, {type_})\n"
            
            # Show in a popup window
            popup = tk.Toplevel(self.root)
            popup.title("Merge Summary")
            popup.geometry("600x400")
            
            text_widget = scrolledtext.ScrolledText(popup, wrap=tk.WORD)
            text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            text_widget.insert(tk.END, summary_text)
            text_widget.config(state=tk.DISABLED)
            
        except Exception as e:
            error_msg = f"Error showing merge summary: {str(e)}"
            self.log_message(error_msg, "ERROR")
            messagebox.showerror("Error", error_msg)
    
    def create_database_after_approval(self, approved_groupings: Dict[str, List[Dict]]):
        """Create the target database with approved versioned groupings"""
        try:
            self.log_message("Creating approved versioned database...")
            
            # Clear target collection
            self.target_col.delete_many({})
            self.log_message("Cleared target collection")
            
            created_count = 0
            total_input_statutes = sum(len(statutes) for statutes in approved_groupings.values())
            total_output_versions = 0
            
            self.log_message(f"Creating versioned database with {len(approved_groupings)} approved groups and {total_input_statutes} total statutes", "DEBUG")
            
            for base_name, statutes in approved_groupings.items():
                original_statute_count = len(statutes)
                self.log_message(f"Group '{base_name}': Creating versioned document with {original_statute_count} statutes", "DEBUG")
                
                group_doc = {
                    "base_name": base_name,
                    "group_id": f"versioned_group_{base_name.lower().replace(' ', '_').replace('-', '_')}",
                    "total_versions": len(statutes),
                    "versions": []
                }
                
                for statute in statutes:
                    # Format the date to DD-MMM-YYYY format
                    raw_date = statute.get("Date", "")
                    formatted_date = format_date_to_dd_mmm_yyyy(raw_date) if raw_date else ""
                    
                    version_doc = {
                        "version_label": statute.get("Version_Label", ""),
                        "statute_name": statute.get("Statute_Name", ""),
                        "date": formatted_date,
                        "statute_type": statute.get("Statute_Type", ""),
                        "province": statute.get("Province", ""),
                        "year": statute.get("Year", ""),
                        "base_name": statute.get("base_name", ""),
                        "sections": statute.get("Sections", []),
                        "original_id": str(statute.get("_id", "")),
                        "act_ordinance": statute.get("Act_Ordinance"),
                        "citations": statute.get("Citations"),
                        "metadata": {
                            k: v for k, v in statute.items() 
                            if k not in ["_id", "Statute_Name", "Date", "Statute_Type", "Sections", "base_name", 
                                        "Act_Ordinance", "Citations", "Province", "Year", "Version_Label"]
                        }
                    }
                    group_doc["versions"].append(version_doc)
                
                final_version_count = len(group_doc["versions"])
                if final_version_count != original_statute_count:
                    self.log_message(f"WARNING: Group '{base_name}': Version count mismatch! Original statutes: {original_statute_count}, Final versions: {final_version_count}", "WARNING")
                
                try:
                    self.target_col.insert_one(group_doc)
                    created_count += 1
                    total_output_versions += final_version_count
                    self.metadata["processing_details"]["groups_created"] += 1
                    self.log_message(f"Group '{base_name}': Successfully created with {final_version_count} versions", "DEBUG")
                except Exception as e:
                    self.log_message(f"Error creating versioned group for {base_name}: {e}", "ERROR")
                
            self.metadata["processing_details"]["database_updates"] = created_count
            
            if total_input_statutes != total_output_versions:
                self.log_message(f"WARNING: Database creation mismatch! Input statutes: {total_input_statutes}, Output versions: {total_output_versions}", "WARNING")
            else:
                self.log_message(f"Database creation complete: {created_count} groups, {total_output_versions} versions", "DEBUG")
            
            # Save versioning info after successful database creation
            self.save_versioning_info(approved_groupings)
            
            # Log comprehensive processing details after database creation
            self._log_comprehensive_processing_details()
            
            return created_count
            
        except Exception as e:
            self.log_message(f"Error creating database after approval: {str(e)}", "ERROR")
            raise e

def format_date_to_dd_mmm_yyyy(date_str: str) -> str:
    """Convert various date formats to DD-MMM-YYYY format"""
    if not date_str or not date_str.strip():
        return ""
    
    date_str = date_str.strip()
    
    # If already in DD-MMM-YYYY format, return as is
    if re.match(r'^\d{1,2}-[A-Za-z]{3}-\d{4}$', date_str):
        return date_str
    
    try:
        # Try different date formats
        date_formats = [
            '%Y-%m-%d',      # YYYY-MM-DD
            '%d/%m/%Y',      # DD/MM/YYYY
            '%m/%d/%Y',      # MM/DD/YYYY
            '%d-%m-%Y',      # DD-MM-YYYY
            '%Y/%m/%d',      # YYYY/MM/DD
            '%d-%m-%y',      # DD-MM-YY
            '%d/%m/%y',      # DD/MM/YY
            '%Y-%m-%d %H:%M:%S',  # YYYY-MM-DD HH:MM:SS
            '%d-%m-%Y %H:%M:%S',  # DD-MM-YYYY HH:MM:SS
            '%d-%b-%Y',      # DD-MMM-YYYY (already formatted)
            '%d %b %Y',      # DD MMM YYYY
            '%d/%b/%Y',      # DD/MMM/YYYY
        ]
        
        parsed_date = None
        for fmt in date_formats:
            try:
                parsed_date = datetime.strptime(date_str, fmt)
                break
            except ValueError:
                continue
        
        if parsed_date:
            # Format as DD-MMM-YYYY
            return parsed_date.strftime('%d-%b-%Y')
        else:
            # Try to handle ordinal dates and other complex formats
            # Handle ordinal dates like "4th March, 2016"
            ordinal_match = re.search(r'(\d{1,2})(st|nd|rd|th)\s+(\w+)\s*,\s*(\d{4})', date_str, re.IGNORECASE)
            if ordinal_match:
                day = ordinal_match.group(1)
                month_name = ordinal_match.group(3)
                year = ordinal_match.group(4)
                try:
                    # Convert month name to number
                    month_num = datetime.strptime(month_name, '%B').month
                    parsed_date = datetime(int(year), month_num, int(day))
                    return parsed_date.strftime('%d-%b-%Y')
                except:
                    pass
            
            # Handle "Month DD, YYYY" format like "March 3, 2016"
            month_day_match = re.search(r'(\w+)\s+(\d{1,2})\s*,\s*(\d{4})', date_str, re.IGNORECASE)
            if month_day_match:
                month_name = month_day_match.group(1)
                day = month_day_match.group(2)
                year = month_day_match.group(3)
                try:
                    # Convert month name to number
                    month_num = datetime.strptime(month_name, '%B').month
                    parsed_date = datetime(int(year), month_num, int(day))
                    return parsed_date.strftime('%d-%b-%Y')
                except:
                    pass
            
            # Handle "DD Month YYYY" format like "3 March 2016"
            day_month_match = re.search(r'(\d{1,2})\s+(\w+)\s+(\d{4})', date_str, re.IGNORECASE)
            if day_month_match:
                day = day_month_match.group(1)
                month_name = day_month_match.group(2)
                year = day_month_match.group(3)
                try:
                    # Convert month name to number
                    month_num = datetime.strptime(month_name, '%B').month
                    parsed_date = datetime(int(year), month_num, int(day))
                    return parsed_date.strftime('%d-%b-%Y')
                except:
                    pass
            
            # Handle "YYYY-MM-DD" format with time
            iso_match = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', date_str)
            if iso_match:
                year = iso_match.group(1)
                month = iso_match.group(2)
                day = iso_match.group(3)
                try:
                    parsed_date = datetime(int(year), int(month), int(day))
                    return parsed_date.strftime('%d-%b-%Y')
                except:
                    pass
            
            # If all parsing fails, try using dateutil parser as last resort
            try:
                parsed_date = parser.parse(date_str, fuzzy=True)
                return parsed_date.strftime('%d-%b-%Y')
            except:
                pass
            
            # If all parsing fails, return original string
            return date_str
            
    except Exception as e:
        print(f"Error formatting date '{date_str}': {e}")
        return date_str

def normalize_for_comparison(text: str) -> str:
    """Normalize text for similarity comparison"""
    if not text:
        return ""
    
    # Convert to lowercase and remove extra whitespace
    normalized = re.sub(r'\s+', ' ', text.lower().strip())
    
    # Remove punctuation except spaces
    normalized = re.sub(r'[^\w\s]', '', normalized)
    
    return normalized

def normalize_province(province: str) -> str:
    """Normalize province name (lowercase, strip)"""
    if not province:
        return ""
    return province.strip().lower()

def calculate_similarity(name1: str, name2: str) -> float:
    """Calculate similarity between two statute names"""
    if not name1 or not name2:
        return 0.0
    
    # Normalize names for comparison
    norm1 = normalize_for_comparison(name1)
    norm2 = normalize_for_comparison(name2)
    
    if norm1 == norm2:
        return 1.0
    
    # Special handling for common variations
    # Replace common variations that should be considered similar
    variations = {
        'layari': 'lyari',
        'lyari': 'layari',
        'karachi': 'karachi',
        'university': 'university',
        'benazir': 'benazir',
        'bhutto': 'bhutto',
        'shaheed': 'shaheed',
        'shaheed': 'shahid',
        'shahid': 'shaheed',
        'act': 'act',
        'amendment': 'amendment',
        'amendment': 'amendments',
        'amendments': 'amendment'
    }
    
    # Apply variations to both normalized strings
    for variant, replacement in variations.items():
        norm1 = norm1.replace(variant, replacement)
        norm2 = norm2.replace(variant, replacement)
    
    # Check if they're identical after applying variations
    if norm1 == norm2:
        return 0.95  # High similarity for known variations
    
    # Use SequenceMatcher for similarity calculation
    matcher = SequenceMatcher(None, norm1, norm2)
    similarity = matcher.ratio()
    
    # Boost similarity for names that are very similar but have slight differences
    if similarity >= 0.8:
        # Check for common patterns that indicate high similarity
        if len(norm1) > 10 and len(norm2) > 10:
            # For longer names, small differences are less significant
            similarity = min(0.95, similarity + 0.05)
    
    return similarity

def main():
    """Main function to run the GUI application"""
    root = tk.Tk()
    
    # Configure ttk styles
    style = ttk.Style()
    if "clam" in style.theme_names():
        style.theme_use("clam")
    
    # Configure custom styles
    style.configure("Accent.TButton", foreground="white", background="#007acc")
    
    app = StatuteVersioningGUI(root)
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("Application interrupted by user")
    except Exception as e:
        print(f"Application error: {e}")

if __name__ == "__main__":
    main()