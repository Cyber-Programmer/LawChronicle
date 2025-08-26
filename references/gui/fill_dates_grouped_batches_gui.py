"""
GUI for Fill Missing Dates in Grouped Batch Databases

This GUI allows users to:
1. Select an Excel file containing statute-date mappings
2. Connect to Batch-Base-Grouped database
3. View statutes with missing dates
4. Fill dates manually with context from sections
5. Update the database and generate metadata
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import openpyxl
from pymongo import MongoClient
import json
import os
from datetime import datetime, date
from collections import defaultdict, Counter
from typing import List, Dict, Optional, Tuple
import threading
from rapidfuzz import process, fuzz
import re

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
            # If parsing fails, return original string
            return date_str
            
    except Exception as e:
        print(f"Error formatting date '{date_str}': {e}")
        return date_str

class FillDatesGroupedBatchesGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Fill Dates - Grouped Batches")
        self.root.geometry("1200x800")
        
        # MongoDB connection
        self.client = None
        self.db = None
        self.col = None
        
        # Data storage
        self.excel_data = []
        self.groups = []
        self.statutes = []
        self.matched_statutes = {}
        self.unmatched_excel = []
        self.unmatched_db = []
        
        # GUI state
        self.current_group_index = -1
        self.current_statute_index = -1
        
        # Configuration
        self.mongo_uri = "mongodb://localhost:27017"
        self.source_db = "Batch-Base-Grouped"
        self.source_coll = "batch1"
        self.target_db = f"{self.source_db}-Filled"
        self.target_coll = self.source_coll
        
        self.init_ui()
        self.connect_to_mongodb()
        
    def init_ui(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=1)
        
        # Top controls frame
        controls_frame = ttk.LabelFrame(main_frame, text="Controls", padding="5")
        controls_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Excel file selection
        ttk.Label(controls_frame, text="Excel File:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.excel_path_var = tk.StringVar()
        ttk.Entry(controls_frame, textvariable=self.excel_path_var, width=50).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 5))
        ttk.Button(controls_frame, text="Browse", command=self.browse_excel).grid(row=0, column=2, padx=(0, 10))
        
        # Database configuration
        ttk.Label(controls_frame, text="Source DB:").grid(row=0, column=3, sticky=tk.W, padx=(10, 5))
        self.source_db_var = tk.StringVar(value=self.source_db)
        self.source_db_combo = ttk.Combobox(controls_frame, textvariable=self.source_db_var, width=15)
        self.source_db_combo.grid(row=0, column=4, padx=(0, 5))
        
        ttk.Label(controls_frame, text="Collection:").grid(row=0, column=5, sticky=tk.W, padx=(5, 5))
        self.source_coll_var = tk.StringVar(value=self.source_coll)
        self.source_coll_combo = ttk.Combobox(controls_frame, textvariable=self.source_coll_var, width=15)
        self.source_coll_combo.grid(row=0, column=6, padx=(0, 5))
        
        ttk.Button(controls_frame, text="Load Data", command=self.load_data).grid(row=0, column=7, padx=(10, 0))
        
        # Status
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(controls_frame, textvariable=self.status_var, foreground="blue").grid(row=1, column=0, columnspan=8, sticky=tk.W, pady=(5, 0))
        
        # Left panel - Groups and Statutes
        left_frame = ttk.LabelFrame(main_frame, text="Groups & Statutes", padding="5")
        left_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        left_frame.columnconfigure(0, weight=1)
        left_frame.rowconfigure(1, weight=1)
        
        # Search and filters
        search_frame = ttk.Frame(left_frame)
        search_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        
        ttk.Label(search_frame, text="Search:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.on_search_change)
        ttk.Entry(search_frame, textvariable=self.search_var, width=30).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        
        self.missing_only_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(search_frame, text="Missing dates only", variable=self.missing_only_var, 
                       command=self.on_search_change).grid(row=0, column=2, padx=(0, 10))
        
        # Groups tree
        ttk.Label(left_frame, text="Groups:").grid(row=1, column=0, sticky=tk.W)
        self.groups_tree = ttk.Treeview(left_frame, columns=("base_name", "province", "type", "total", "missing"), 
                                       show="tree headings", height=10)
        self.groups_tree.heading("#0", text="Group ID")
        self.groups_tree.heading("base_name", text="Base Name")
        self.groups_tree.heading("province", text="Province")
        self.groups_tree.heading("type", text="Type")
        self.groups_tree.heading("total", text="Total")
        self.groups_tree.heading("missing", text="Missing")
        
        self.groups_tree.column("#0", width=150)
        self.groups_tree.column("base_name", width=120)
        self.groups_tree.column("province", width=80)
        self.groups_tree.column("type", width=60)
        self.groups_tree.column("total", width=50)
        self.groups_tree.column("missing", width=60)
        
        groups_scroll = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.groups_tree.yview)
        self.groups_tree.configure(yscrollcommand=groups_scroll.set)
        
        self.groups_tree.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        groups_scroll.grid(row=2, column=1, sticky=(tk.N, tk.S))
        
        self.groups_tree.bind('<<TreeviewSelect>>', self.on_group_select)
        
        # Statutes tree
        ttk.Label(left_frame, text="Statutes:").grid(row=3, column=0, sticky=tk.W, pady=(10, 0))
        self.statutes_tree = ttk.Treeview(left_frame, columns=("name", "date", "status"), 
                                         show="tree headings", height=8)
        self.statutes_tree.heading("#0", text="ID")
        self.statutes_tree.heading("name", text="Statute Name")
        self.statutes_tree.heading("date", text="Date")
        self.statutes_tree.heading("status", text="Status")
        
        self.statutes_tree.column("#0", width=100)
        self.statutes_tree.column("name", width=300)
        self.statutes_tree.column("date", width=100)
        self.statutes_tree.column("status", width=80)
        
        statutes_scroll = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.statutes_tree.yview)
        self.statutes_tree.configure(yscrollcommand=statutes_scroll.set)
        
        self.statutes_tree.grid(row=4, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        statutes_scroll.grid(row=4, column=1, sticky=(tk.N, tk.S))
        
        self.statutes_tree.bind('<<TreeviewSelect>>', self.on_statute_select)
        
        # Right panel - Details and Editing
        right_frame = ttk.LabelFrame(main_frame, text="Details & Editing", padding="5")
        right_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(2, weight=1)
        
        # Statute info
        info_frame = ttk.Frame(right_frame)
        info_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(info_frame, text="Statute Name:").grid(row=0, column=0, sticky=tk.W)
        self.statute_name_var = tk.StringVar()
        ttk.Entry(info_frame, textvariable=self.statute_name_var, width=50).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 0))
        
        ttk.Label(info_frame, text="Current Date:").grid(row=1, column=0, sticky=tk.W, pady=(5, 0))
        self.current_date_var = tk.StringVar()
        ttk.Entry(info_frame, textvariable=self.current_date_var, width=20).grid(row=1, column=1, sticky=tk.W, padx=(5, 10), pady=(5, 0))
        
        ttk.Label(info_frame, text="New Date:").grid(row=1, column=2, sticky=tk.W, pady=(5, 0))
        self.new_date_var = tk.StringVar()
        ttk.Entry(info_frame, textvariable=self.new_date_var, width=20).grid(row=1, column=3, sticky=tk.W, padx=(5, 0), pady=(5, 0))
        
        ttk.Button(info_frame, text="Update Date", command=self.update_date).grid(row=1, column=4, padx=(10, 0), pady=(5, 0))
        
        # Sections
        ttk.Label(right_frame, text="Sections:").grid(row=1, column=0, sticky=tk.W)
        
        sections_frame = ttk.Frame(right_frame)
        sections_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        sections_frame.columnconfigure(0, weight=1)
        sections_frame.rowconfigure(1, weight=1)
        
        # Section dropdown
        self.section_var = tk.StringVar()
        self.section_combo = ttk.Combobox(sections_frame, textvariable=self.section_var, state="readonly")
        self.section_combo.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        self.section_combo.bind('<<ComboboxSelected>>', self.on_section_select)
        
        # Section text
        self.section_text = scrolledtext.ScrolledText(sections_frame, height=15, wrap=tk.WORD)
        self.section_text.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Bottom buttons
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
        
        ttk.Button(bottom_frame, text="Save to Database", command=self.save_to_database).grid(row=0, column=0, padx=(0, 10))
        ttk.Button(bottom_frame, text="Generate Metadata", command=self.generate_metadata).grid(row=0, column=1, padx=(0, 10))
        ttk.Button(bottom_frame, text="Export Unmatched", command=self.export_unmatched).grid(row=0, column=2, padx=(0, 10))
        ttk.Button(bottom_frame, text="Refresh", command=self.refresh_data).grid(row=0, column=3)
        
        # Progress bar
        self.progress_var = tk.StringVar(value="Ready")
        ttk.Label(bottom_frame, textvariable=self.progress_var).grid(row=1, column=0, columnspan=4, sticky=tk.W, pady=(5, 0))
        
    def connect_to_mongodb(self):
        """Connect to MongoDB and load databases/collections"""
        try:
            self.client = MongoClient(self.mongo_uri)
            self.client.admin.command('ping')
            
            # Load databases
            databases = self.client.list_database_names()
            self.source_db_combo['values'] = databases
            
            # Set current database
            if self.source_db in databases:
                self.source_db_combo.set(self.source_db)
            elif databases:
                self.source_db_combo.set(databases[0])
                self.source_db = databases[0]
            
            self.source_db_combo.bind('<<ComboboxSelected>>', self.on_db_change)
            
            self.status_var.set("Connected to MongoDB")
            
        except Exception as e:
            messagebox.showerror("Connection Error", f"Failed to connect to MongoDB: {e}")
            self.status_var.set("Connection failed")
    
    def on_db_change(self, event=None):
        """Handle database change"""
        try:
            db_name = self.source_db_combo.get()
            if db_name:
                self.source_db = db_name
                db = self.client[db_name]
                collections = db.list_collection_names()
                self.source_coll_combo['values'] = collections
                
                if collections:
                    self.source_coll_combo.set(collections[0])
                    self.source_coll = collections[0]
                
                self.source_coll_combo.bind('<<ComboboxSelected>>', self.on_collection_change)
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load collections: {e}")
    
    def on_collection_change(self, event=None):
        """Handle collection change"""
        try:
            coll_name = self.source_coll_combo.get()
            if coll_name:
                self.source_coll = coll_name
                self.target_coll = coll_name
                self.target_db = f"{self.source_db}-Filled"
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to change collection: {e}")
    
    def browse_excel(self):
        """Browse for Excel file"""
        filename = filedialog.askopenfilename(
            title="Select Excel File",
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")]
        )
        if filename:
            self.excel_path_var.set(filename)
    
    def load_data(self):
        """Load Excel data and database data"""
        def load_thread():
            try:
                self.progress_var.set("Loading Excel data...")
                
                # Load Excel data
                excel_path = self.excel_path_var.get()
                if not excel_path or not os.path.exists(excel_path):
                    messagebox.showerror("Error", "Please select a valid Excel file")
                    return
                
                self.excel_data = self.load_excel_data(excel_path)
                
                self.progress_var.set("Loading database data...")
                
                # Load database data
                self.db = self.client[self.source_db]
                self.col = self.db[self.source_coll]
                
                self.groups, self.statutes, missing_count = self.get_grouped_statutes_with_missing_dates()
                
                self.progress_var.set("Matching data...")
                
                # Match statutes to Excel data
                self.matched_statutes, self.unmatched_excel, self.unmatched_db = self.match_statutes_to_excel(
                    self.statutes, self.excel_data
                )
                
                self.root.after(0, self.update_ui)
                self.root.after(0, lambda: self.progress_var.set("Data loaded successfully"))
                
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to load data: {e}"))
                self.root.after(0, lambda: self.progress_var.set("Error loading data"))
        
        threading.Thread(target=load_thread, daemon=True).start()
    
    def load_excel_data(self, excel_file_path: str) -> List[Dict]:
        """Load data from Excel file"""
        try:
            workbook = openpyxl.load_workbook(excel_file_path, data_only=True)
            sheet = workbook.active
            
            data = []
            headers = []
            
            for row_idx, row in enumerate(sheet.iter_rows(values_only=True), 1):
                if row_idx == 1:  # Header row
                    headers = [str(cell).strip() if cell else "" for cell in row]
                    continue
                
                if not any(cell for cell in row):  # Skip empty rows
                    continue
                
                row_data = {}
                for col_idx, cell in enumerate(row):
                    if col_idx < len(headers):
                        header = headers[col_idx]
                        value = cell.strip() if isinstance(cell, str) else str(cell) if cell is not None else ""
                        
                        # Format dates if this is a date column
                        if header.lower() in ['date', 'best_date', 'all_dates_extracted']:
                            value = format_date_to_dd_mmm_yyyy(value)
                        
                        row_data[header] = value
                
                if row_data:
                    data.append(row_data)
            
            return data
            
        except Exception as e:
            raise Exception(f"Failed to load Excel file: {e}")
    
    def get_grouped_statutes_with_missing_dates(self) -> Tuple[List[Dict], List[Dict], int]:
        """Get grouped statutes from database with missing dates count"""
        try:
            groups = list(self.col.find({}))
            statutes = []
            missing_count = 0
            
            for group in groups:
                group_statutes = group.get('statutes', [])
                for statute in group_statutes:
                    statute['group_id'] = group.get('_id')
                    statute['base_name'] = group.get('base_name')
                    statute['province'] = group.get('province')
                    statute['statute_type'] = group.get('statute_type')
                    statutes.append(statute)
                    
                    if not statute.get('Date'):
                        missing_count += 1
            
            return groups, statutes, missing_count
            
        except Exception as e:
            raise Exception(f"Failed to load grouped statutes: {e}")
    
    def match_statutes_to_excel(self, statutes: List[Dict], excel_data: List[Dict]) -> Tuple[Dict, List, List]:
        """Match statutes to Excel data using fuzzy matching"""
        matched = {}
        unmatched_excel = []
        unmatched_db = []
        
        # Create Excel lookup dictionary
        excel_lookup = {}
        for row in excel_data:
            statute_name = row.get('Statute_Name', '').strip()
            date_value = row.get('Date', '').strip()
            if statute_name and date_value:
                excel_lookup[statute_name.lower()] = {
                    'name': statute_name,
                    'date': date_value,
                    'row': row
                }
        
        # Match statutes
        for statute in statutes:
            statute_name = statute.get('Statute_Name', '').strip()
            if not statute_name:
                continue
            
            # Try exact match first
            if statute_name.lower() in excel_lookup:
                matched[statute['_id']] = excel_lookup[statute_name.lower()]
            else:
                # Try fuzzy matching
                excel_names = list(excel_lookup.keys())
                if excel_names:
                    matches = process.extract(
                        statute_name.lower(),
                        excel_names,
                        scorer=fuzz.WRatio,
                        limit=1
                    )
                    
                    if matches and matches[0][1] > 80:  # High confidence threshold
                        best_match = matches[0][0]
                        matched[statute['_id']] = excel_lookup[best_match]
                    else:
                        unmatched_db.append(statute)
                else:
                    unmatched_db.append(statute)
        
        # Find unmatched Excel entries
        matched_excel_names = {data['name'].lower() for data in matched.values()}
        for row in excel_data:
            statute_name = row.get('Statute_Name', '').strip()
            if statute_name and statute_name.lower() not in matched_excel_names:
                unmatched_excel.append(row)
        
        return matched, unmatched_excel, unmatched_db
    
    def update_ui(self):
        """Update the UI with loaded data"""
        # Clear existing data
        for tree in [self.groups_tree, self.statutes_tree]:
            for item in tree.get_children():
                tree.delete(item)
        
        # Populate groups tree
        filtered_groups = self.filter_groups()
        for group in filtered_groups:
            group_id = str(group.get('_id', ''))[:8] + "..."
            base_name = group.get('base_name', '')
            province = group.get('province', '')
            statute_type = group.get('statute_type', '')
            total_statutes = len(group.get('statutes', []))
            
            # Count missing dates
            missing_count = sum(1 for statute in group.get('statutes', []) 
                              if not statute.get('Date'))
            
            self.groups_tree.insert('', 'end', text=group_id, values=(
                base_name, province, statute_type, total_statutes, missing_count
            ))
        
        self.status_var.set(f"Loaded {len(self.groups)} groups, {len(self.statutes)} statutes")
    
    def filter_groups(self):
        """Filter groups based on search criteria"""
        search_text = self.search_var.get().lower()
        missing_only = self.missing_only_var.get()
        
        filtered = []
        for group in self.groups:
            # Check if group has missing dates
            has_missing = any(not statute.get('Date') for statute in group.get('statutes', []))
            
            if missing_only and not has_missing:
                continue
            
            # Check search text
            if search_text:
                base_name = group.get('base_name', '').lower()
                group_id = str(group.get('_id', '')).lower()
                if search_text not in base_name and search_text not in group_id:
                    continue
            
            filtered.append(group)
        
        return filtered
    
    def on_search_change(self, *args):
        """Handle search/filter changes"""
        self.update_ui()
    
    def on_group_select(self, event):
        """Handle group selection"""
        selection = self.groups_tree.selection()
        if not selection:
            return
        
        # Find the selected group
        group_id = self.groups_tree.item(selection[0])['text']
        for i, group in enumerate(self.groups):
            if str(group.get('_id', ''))[:8] + "..." == group_id:
                self.current_group_index = i
                self.update_statutes_tree(group)
                break
    
    def update_statutes_tree(self, group):
        """Update statutes tree for selected group"""
        # Clear existing items
        for item in self.statutes_tree.get_children():
            self.statutes_tree.delete(item)
        
        statutes = group.get('statutes', [])
        for statute in statutes:
            statute_id = str(statute.get('_id', ''))[:8] + "..."
            name = statute.get('Statute_Name', '')
            date = statute.get('Date', '')
            
            # Format date for display
            formatted_date = format_date_to_dd_mmm_yyyy(date) if date else ''
            
            # Determine status
            if date:
                status = "✓ Complete"
                icon = "✓"
            else:
                status = "📅 Missing"
                icon = "📅"
            
            self.statutes_tree.insert('', 'end', text=icon, values=(
                statute_id, name, formatted_date, status
            ))
    
    def on_statute_select(self, event):
        """Handle statute selection"""
        selection = self.statutes_tree.selection()
        if not selection:
            return
        
        # Find the selected statute
        statute_id = self.statutes_tree.item(selection[0])['values'][0]
        if self.current_group_index >= 0:
            group = self.groups[self.current_group_index]
            statutes = group.get('statutes', [])
            
            for i, statute in enumerate(statutes):
                if str(statute.get('_id', ''))[:8] + "..." == statute_id:
                    self.current_statute_index = i
                    self.update_statute_details(statute)
                    break
    
    def update_statute_details(self, statute):
        """Update statute details panel"""
        self.statute_name_var.set(statute.get('Statute_Name', ''))
        
        # Format and display current date
        current_date = statute.get('Date', '')
        formatted_current_date = format_date_to_dd_mmm_yyyy(current_date)
        self.current_date_var.set(formatted_current_date)
        
        # Check if we have a matched date from Excel
        statute_id = statute.get('_id')
        if statute_id in self.matched_statutes:
            matched_data = self.matched_statutes[statute_id]
            formatted_matched_date = format_date_to_dd_mmm_yyyy(matched_data['date'])
            self.new_date_var.set(formatted_matched_date)
        else:
            self.new_date_var.set('')
        
        # Update sections
        sections = statute.get('Sections', [])
        section_names = [section.get('Section', '') for section in sections if section.get('Section')]
        
        self.section_combo['values'] = section_names
        if section_names:
            self.section_combo.set(section_names[0])
            self.on_section_select()
    
    def on_section_select(self, event=None):
        """Handle section selection"""
        if self.current_group_index < 0 or self.current_statute_index < 0:
            return
        
        group = self.groups[self.current_group_index]
        statute = group['statutes'][self.current_statute_index]
        
        selected_section = self.section_var.get()
        sections = statute.get('Sections', [])
        
        for section in sections:
            if section.get('Section') == selected_section:
                self.section_text.delete(1.0, tk.END)
                self.section_text.insert(1.0, section.get('Statute', ''))
                break
    
    def update_date(self):
        """Update date for current statute"""
        if self.current_group_index < 0 or self.current_statute_index < 0:
            messagebox.showwarning("Warning", "Please select a statute first")
            return
        
        new_date = self.new_date_var.get().strip()
        if not new_date:
            messagebox.showwarning("Warning", "Please enter a date")
            return
        
        # Format the date to DD-MMM-YYYY
        formatted_date = format_date_to_dd_mmm_yyyy(new_date)
        
        # Update the statute in memory
        group = self.groups[self.current_group_index]
        statute = group['statutes'][self.current_statute_index]
        statute['Date'] = formatted_date
        
        # Update the UI
        self.update_statutes_tree(group)
        self.current_date_var.set(formatted_date)
        
        messagebox.showinfo("Success", f"Date updated to: {formatted_date}")
    
    def save_to_database(self):
        """Save updated groups to target database"""
        def save_thread():
            try:
                self.progress_var.set("Saving to database...")
                
                # Create target database and collection
                target_db = self.client[self.target_db]
                target_col = target_db[self.target_coll]
                
                # Drop existing collection if it exists
                target_col.drop()
                
                # Insert updated groups
                target_col.insert_many(self.groups)
                
                self.root.after(0, lambda: messagebox.showinfo("Success", 
                    f"Data saved to {self.target_db}.{self.target_coll}"))
                self.root.after(0, lambda: self.progress_var.set("Data saved successfully"))
                
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to save: {e}"))
                self.root.after(0, lambda: self.progress_var.set("Error saving data"))
        
        threading.Thread(target=save_thread, daemon=True).start()
    
    def generate_metadata(self):
        """Generate metadata summary"""
        try:
            metadata = {
                "script": "fill_dates_grouped_batches_gui.py",
                "execution_date": datetime.now().isoformat(),
                "source_database": f"{self.source_db}.{self.source_coll}",
                "target_database": f"{self.target_db}.{self.target_coll}",
                "processing_stats": {
                    "total_groups": len(self.groups),
                    "total_statutes": len(self.statutes),
                    "matched_statutes": len(self.matched_statutes),
                    "unmatched_excel": len(self.unmatched_excel),
                    "unmatched_db": len(self.unmatched_db)
                },
                "excel_analysis": {
                    "total_excel_rows": len(self.excel_data),
                    "valid_excel_rows": len([row for row in self.excel_data if row.get('Statute_Name') and row.get('Date')])
                }
            }
            
            # Save metadata
            os.makedirs("metadata", exist_ok=True)
            metadata_file = f"metadata/fill_dates_grouped_batches_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            messagebox.showinfo("Success", f"Metadata saved to {metadata_file}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate metadata: {e}")
    
    def export_unmatched(self):
        """Export unmatched statutes to CSV"""
        try:
            import csv
            
            os.makedirs("exports", exist_ok=True)
            export_file = f"exports/unmatched_statutes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
            with open(export_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Type', 'Statute_Name', 'Date', 'Province', 'Statute_Type'])
                
                # Write unmatched Excel entries
                for row in self.unmatched_excel:
                    writer.writerow(['Excel', row.get('Statute_Name', ''), row.get('Date', ''), '', ''])
                
                # Write unmatched DB entries
                for statute in self.unmatched_db:
                    writer.writerow(['Database', statute.get('Statute_Name', ''), statute.get('Date', ''), 
                                   statute.get('Province', ''), statute.get('Statute_Type', '')])
            
            messagebox.showinfo("Success", f"Unmatched statutes exported to {export_file}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export unmatched: {e}")
    
    def refresh_data(self):
        """Refresh data from database"""
        self.load_data()

def main():
    root = tk.Tk()
    app = FillDatesGroupedBatchesGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main() 