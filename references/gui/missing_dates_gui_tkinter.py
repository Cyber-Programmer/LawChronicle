"""
Missing Dates GUI - Tkinter Interface with NumPy Support

A GUI application for checking and filling missing dates in grouped batch databases.
Allows users to browse statutes with missing dates, view their sections, and fill in dates.

Features:
- Browse statutes with missing dates
- View statute sections and content
- Fill missing dates with validation
- Real-time updates to database
- Search and filter functionality with NumPy optimization
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from pymongo import MongoClient
import json
from datetime import datetime
from typing import List, Dict, Optional
import re
import numpy as np
from rapidfuzz import process, fuzz

# --- MongoDB Config ---
MONGO_URI = "mongodb://localhost:27017/"
DEFAULT_DB = "Batch-Base-Grouped-Filled"
DEFAULT_COLL = "batch2"

class MissingDatesGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Missing Dates Manager")
        self.root.geometry("1200x800")
        
        # Data storage
        self.client = None
        self.db = None
        self.col = None
        self.groups = []
        self.all_statutes = []
        self.current_statute = None
        self.filtered_statutes = []
        
        # NumPy arrays for efficient filtering
        self.statute_names_array = None
        self.missing_dates_mask = None
        self.missing_names_mask = None
        self.provinces_array = None
        self.types_array = None
        
        # Initialize UI
        self.init_db()
        self.init_ui()
        self.load_databases()
        self.load_data()
        
    def init_db(self):
        """Initialize MongoDB connection"""
        try:
            self.client = MongoClient(MONGO_URI)
            self.client.admin.command('ping')
            self.db = self.client[DEFAULT_DB]
            self.col = self.db[DEFAULT_COLL]
            print(f"Connected to {DEFAULT_DB}.{DEFAULT_COLL}")
            
        except Exception as e:
            messagebox.showerror("DB Error", f"Could not connect to MongoDB: {e}")
            
    def load_databases(self):
        """Load available databases and collections"""
        try:
            # Get all databases
            databases = self.client.list_database_names()
            self.db_dropdown['values'] = databases
            
            # Set current database
            current_db_index = self.db_dropdown['values'].index(DEFAULT_DB) if DEFAULT_DB in self.db_dropdown['values'] else 0
            self.db_dropdown.current(current_db_index)
            
            self.load_collections()
            
        except Exception as e:
            messagebox.showwarning("Warning", f"Could not load databases: {e}")
            
    def load_collections(self):
        """Load collections for the selected database"""
        try:
            current_db = self.db_var.get()
            if current_db:
                db = self.client[current_db]
                collections = db.list_collection_names()
                self.col_dropdown['values'] = collections
                
                # Set current collection
                current_col_index = self.col_dropdown['values'].index(DEFAULT_COLL) if DEFAULT_COLL in self.col_dropdown['values'] else 0
                self.col_dropdown.current(current_col_index)
                    
        except Exception as e:
            messagebox.showwarning("Warning", f"Could not load collections: {e}")
            
    def on_db_change(self, event=None):
        """Handle database change"""
        if self.db_var.get():
            self.load_collections()
            self.connection_status.config(text=f"Connected to {self.db_var.get()}", foreground="green")
            
    def on_collection_change(self, event=None):
        """Handle collection change"""
        if self.col_var.get():
            current_db = self.db_var.get()
            self.connection_status.config(text=f"Connected to {current_db}.{self.col_var.get()}", foreground="green")
            self.refresh_data()
            
    def refresh_data(self):
        """Refresh data from the selected database and collection"""
        try:
            current_db = self.db_var.get()
            current_collection = self.col_var.get()
            
            if current_db and current_collection:
                self.db = self.client[current_db]
                self.col = self.db[current_collection]
                
                # Clear current data
                self.groups = []
                self.all_statutes = []
                self.filtered_statutes = []
                self.current_statute = None
                
                # Clear NumPy arrays
                self.statute_names_array = None
                self.missing_dates_mask = None
                self.missing_names_mask = None
                self.provinces_array = None
                self.types_array = None
                
                # Reload data
                self.load_data()
                
                self.connection_status.config(text=f"Connected to {current_db}.{current_collection} - Data refreshed", foreground="green")
                
                messagebox.showinfo("Success", f"Data refreshed from {current_db}.{current_collection}")
            else:
                messagebox.showwarning("Warning", "Please select both database and collection")
                
        except Exception as e:
            self.connection_status.config(text=f"Error: {str(e)}", foreground="red")
            messagebox.showerror("Error", f"Could not refresh data: {e}")
            
    def init_ui(self):
        """Initialize the user interface"""
        # Main layout
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Left panel - Controls and Statistics
        left_frame = ttk.Frame(main_frame, width=350)
        left_frame.pack(side="left", fill="y", padx=(0, 10))
        left_frame.pack_propagate(False)
        
        # Right panel - Statute details
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side="right", fill="both", expand=True)
        
        self.setup_left_panel(left_frame)
        self.setup_right_panel(right_frame)
        
    def setup_left_panel(self, parent):
        """Setup the left control panel"""
        # Title
        title_label = ttk.Label(parent, text="Missing Dates Manager", font=("Arial", 16, "bold"))
        title_label.pack(pady=10)
        
        # Database Configuration Panel
        config_frame = ttk.LabelFrame(parent, text="Database Configuration")
        config_frame.pack(fill="x", pady=5)
        
        # Database dropdown
        ttk.Label(config_frame, text="Database:").pack(anchor="w", padx=10, pady=2)
        self.db_var = tk.StringVar(value=DEFAULT_DB)
        self.db_dropdown = ttk.Combobox(config_frame, textvariable=self.db_var, state="readonly")
        self.db_dropdown.pack(fill="x", padx=10, pady=2)
        self.db_dropdown.bind("<<ComboboxSelected>>", self.on_db_change)
        
        # Collection dropdown
        ttk.Label(config_frame, text="Collection:").pack(anchor="w", padx=10, pady=2)
        self.col_var = tk.StringVar(value=DEFAULT_COLL)
        self.col_dropdown = ttk.Combobox(config_frame, textvariable=self.col_var, state="readonly")
        self.col_dropdown.pack(fill="x", padx=10, pady=2)
        self.col_dropdown.bind("<<ComboboxSelected>>", self.on_collection_change)
        
        # Connection status
        self.connection_status = ttk.Label(config_frame, text="Connected", foreground="green")
        self.connection_status.pack(anchor="w", padx=10, pady=2)
        
        # Statistics
        stats_frame = ttk.LabelFrame(parent, text="Statistics")
        stats_frame.pack(fill="x", pady=5)
        
        self.total_groups_label = ttk.Label(stats_frame, text="Total Groups: 0")
        self.total_groups_label.pack(anchor="w", padx=10, pady=2)
        
        self.total_statutes_label = ttk.Label(stats_frame, text="Total Statutes: 0")
        self.total_statutes_label.pack(anchor="w", padx=10, pady=2)
        
        self.missing_dates_label = ttk.Label(stats_frame, text="Missing Dates: 0", foreground="red")
        self.missing_dates_label.pack(anchor="w", padx=10, pady=2)
        
        self.missing_names_label = ttk.Label(stats_frame, text="Missing Names: 0", foreground="red")
        self.missing_names_label.pack(anchor="w", padx=10, pady=2)
        
        self.completion_label = ttk.Label(stats_frame, text="Completion: 0%")
        self.completion_label.pack(anchor="w", padx=10, pady=2)
        
        # Search
        search_frame = ttk.LabelFrame(parent, text="Search")
        search_frame.pack(fill="x", pady=5)
        
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        self.search_entry.pack(fill="x", padx=10, pady=5)
        self.search_var.trace("w", lambda *args: self.on_search())
        
        # Filters
        filter_frame = ttk.LabelFrame(parent, text="Filters")
        filter_frame.pack(fill="x", pady=5)
        
        # Missing date filter
        self.missing_date_var = tk.BooleanVar(value=True)
        missing_date_checkbox = ttk.Checkbutton(filter_frame, text="Show only statutes with missing dates", 
                                               variable=self.missing_date_var, command=self.on_filter_change)
        missing_date_checkbox.pack(anchor="w", padx=10, pady=2)
        
        # Missing name filter
        self.missing_name_var = tk.BooleanVar(value=False)
        missing_name_checkbox = ttk.Checkbutton(filter_frame, text="Show only statutes with missing names", 
                                               variable=self.missing_name_var, command=self.on_filter_change)
        missing_name_checkbox.pack(anchor="w", padx=10, pady=2)
        
        # Province filter
        ttk.Label(filter_frame, text="Province:").pack(anchor="w", padx=10, pady=2)
        self.province_var = tk.StringVar(value="All Provinces")
        self.province_dropdown = ttk.Combobox(filter_frame, textvariable=self.province_var, state="readonly")
        self.province_dropdown.pack(fill="x", padx=10, pady=2)
        self.province_dropdown.bind("<<ComboboxSelected>>", lambda e: self.on_filter_change())
        
        # Type filter
        ttk.Label(filter_frame, text="Statute Type:").pack(anchor="w", padx=10, pady=2)
        self.type_var = tk.StringVar(value="All Types")
        self.type_dropdown = ttk.Combobox(filter_frame, textvariable=self.type_var, state="readonly")
        self.type_dropdown.pack(fill="x", padx=10, pady=2)
        self.type_dropdown.bind("<<ComboboxSelected>>", lambda e: self.on_filter_change())
        
        # Buttons
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill="x", pady=5)
        
        self.refresh_btn = ttk.Button(button_frame, text="Refresh Data", command=self.refresh_data)
        self.refresh_btn.pack(fill="x", pady=2)
        
        # Statutes list
        list_frame = ttk.LabelFrame(parent, text="Statutes List")
        list_frame.pack(fill="both", expand=True, pady=5)
        
        # Create Treeview for statutes list
        self.statutes_tree = ttk.Treeview(list_frame, columns=("name", "province", "type"), show="tree headings")
        self.statutes_tree.heading("#0", text="Status")
        self.statutes_tree.heading("name", text="Name")
        self.statutes_tree.heading("province", text="Province")
        self.statutes_tree.heading("type", text="Type")
        
        self.statutes_tree.column("#0", width=50)
        self.statutes_tree.column("name", width=200)
        self.statutes_tree.column("province", width=80)
        self.statutes_tree.column("type", width=80)
        
        # Scrollbar for treeview
        tree_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.statutes_tree.yview)
        self.statutes_tree.configure(yscrollcommand=tree_scrollbar.set)
        
        self.statutes_tree.pack(side="left", fill="both", expand=True)
        tree_scrollbar.pack(side="right", fill="y")
        
        self.statutes_tree.bind("<<TreeviewSelect>>", self.on_statute_select)
        
    def setup_right_panel(self, parent):
        """Setup the right details panel"""
        # Header with editing controls
        header_frame = ttk.Frame(parent)
        header_frame.pack(fill="x", pady=5)
        
        # Statute name and editing
        name_frame = ttk.LabelFrame(header_frame, text="Statute Name")
        name_frame.pack(fill="x", pady=5)
        
        self.name_var = tk.StringVar()
        self.name_entry = ttk.Entry(name_frame, textvariable=self.name_var, width=50)
        self.name_entry.pack(side="left", padx=5, pady=5)
        
        self.save_name_btn = ttk.Button(name_frame, text="Save Name", command=self.save_name)
        self.save_name_btn.pack(side="left", padx=5, pady=5)
        
        # Date editing
        date_frame = ttk.LabelFrame(header_frame, text="Date")
        date_frame.pack(fill="x", pady=5)
        
        self.date_var = tk.StringVar()
        self.date_entry = ttk.Entry(date_frame, textvariable=self.date_var, width=20)
        self.date_entry.pack(side="left", padx=5, pady=5)
        
        ttk.Label(date_frame, text="(YYYY-MM-DD)").pack(side="left", padx=5, pady=5)
        
        self.save_date_btn = ttk.Button(date_frame, text="Save Date", command=self.save_date)
        self.save_date_btn.pack(side="left", padx=5, pady=5)
        
        # Delete statute button
        delete_frame = ttk.LabelFrame(header_frame, text="Delete Statute")
        delete_frame.pack(fill="x", pady=5)
        
        self.delete_btn = ttk.Button(delete_frame, text="Delete Selected Statute", command=self.delete_statute, style="Danger.TButton")
        self.delete_btn.pack(padx=5, pady=5)
        
        # Statute info
        info_frame = ttk.LabelFrame(parent, text="Statute Information")
        info_frame.pack(fill="x", pady=5)
        
        self.statute_info_label = ttk.Label(info_frame, text="Select a statute to view details")
        self.statute_info_label.pack(anchor="w", padx=10, pady=5)
        
        # Sections
        sections_frame = ttk.LabelFrame(parent, text="Sections")
        sections_frame.pack(fill="both", expand=True, pady=5)
        
        # Section dropdown
        section_select_frame = ttk.Frame(sections_frame)
        section_select_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(section_select_frame, text="Section:").pack(side="left")
        self.section_var = tk.StringVar()
        self.section_dropdown = ttk.Combobox(section_select_frame, textvariable=self.section_var, state="readonly", width=30)
        self.section_dropdown.pack(side="left", padx=5)
        self.section_dropdown.bind("<<ComboboxSelected>>", self.on_section_select)
        
        # Section text
        self.sections_text = scrolledtext.ScrolledText(sections_frame, height=20, wrap=tk.WORD)
        self.sections_text.pack(fill="both", expand=True, padx=10, pady=5)
        
    def load_data(self):
        """Load data from database with NumPy optimization"""
        try:
            # Load all groups
            self.groups = list(self.col.find({}))
            
            # Debug: Check what's in the database
            count = self.col.count_documents({})
            print(f"DEBUG: Database has {count} documents")
            
            if count > 0:
                # Look at first document structure
                first_doc = self.col.find_one({})
                print(f"DEBUG: First document keys: {list(first_doc.keys())}")
                if "statutes" in first_doc:
                    print(f"DEBUG: First group has {len(first_doc['statutes'])} statutes")
                    if first_doc['statutes']:
                        first_statute = first_doc['statutes'][0]
                        print(f"DEBUG: First statute keys: {list(first_statute.keys())}")
                        print(f"DEBUG: First statute name: {first_statute.get('Statute_Name', 'No name')}")
                        print(f"DEBUG: First statute date: {first_statute.get('Date', 'No date')}")
            
            # Extract all statutes
            self.all_statutes = []
            total_statutes = 0
            missing_dates_count = 0
            missing_names_count = 0
            
            provinces = set()
            types = set()
            
            for group in self.groups:
                statutes = group.get("statutes", [])
                total_statutes += len(statutes)
                
                for statute in statutes:
                    # Check for missing date
                    date_field = statute.get("Date", "")
                    has_missing_date = not date_field or str(date_field).strip() == ""
                    
                    # Check for missing name
                    name_field = statute.get("Statute_Name", "")
                    has_missing_name = not name_field or str(name_field).strip() == ""
                    
                    if has_missing_date:
                        missing_dates_count += 1
                    if has_missing_name:
                        missing_names_count += 1
                    
                    # Add group context
                    statute_with_context = {
                        **statute,
                        "_group_id": group["_id"],
                        "_group_base_name": group.get("base_name", ""),
                        "_group_province": group.get("province", ""),
                        "_group_statute_type": group.get("statute_type", ""),
                        "_has_missing_date": has_missing_date,
                        "_has_missing_name": has_missing_name
                    }
                    self.all_statutes.append(statute_with_context)
                    
                    # Collect filter options
                    provinces.add(group.get("province", "Unknown"))
                    types.add(group.get("statute_type", "Unknown"))
            
            # Create NumPy arrays for efficient filtering
            self.create_numpy_arrays()
            
            # Update statistics
            self.update_statistics(len(self.groups), total_statutes, missing_dates_count, missing_names_count)
            
            # Update filter dropdowns
            self.update_filters(list(provinces), list(types))
            
            # Update list
            self.update_statutes_list()
            
            print(f"DEBUG: Loaded {len(self.groups)} groups, {total_statutes} total statutes")
            print(f"DEBUG: Missing dates: {missing_dates_count}, Missing names: {missing_names_count}")
            print(f"DEBUG: All statutes loaded: {len(self.all_statutes)}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error loading data: {e}")
            print(f"DEBUG ERROR: {e}")
            
    def create_numpy_arrays(self):
        """Create NumPy arrays for efficient filtering"""
        if not self.all_statutes:
            return
            
        # Create arrays for efficient filtering
        self.statute_names_array = np.array([s.get("Statute_Name", "") for s in self.all_statutes])
        self.missing_dates_mask = np.array([s.get("_has_missing_date", False) for s in self.all_statutes])
        self.missing_names_mask = np.array([s.get("_has_missing_name", False) for s in self.all_statutes])
        self.provinces_array = np.array([s.get("_group_province", "") for s in self.all_statutes])
        self.types_array = np.array([s.get("_group_statute_type", "") for s in self.all_statutes])
        
        print(f"DEBUG: Created NumPy arrays with shape: {self.statute_names_array.shape}")
            
    def update_statistics(self, total_groups, total_statutes, missing_dates_count, missing_names_count):
        """Update statistics display"""
        date_completion = ((total_statutes - missing_dates_count) / total_statutes * 100) if total_statutes > 0 else 0
        name_completion = ((total_statutes - missing_names_count) / total_statutes * 100) if total_statutes > 0 else 0
        
        self.total_groups_label.config(text=f"Total Groups: {total_groups}")
        self.total_statutes_label.config(text=f"Total Statutes: {total_statutes}")
        self.missing_dates_label.config(text=f"Missing Dates: {missing_dates_count}")
        self.missing_names_label.config(text=f"Missing Names: {missing_names_count}")
        self.completion_label.config(text=f"Date Completion: {date_completion:.1f}% | Name Completion: {name_completion:.1f}%")
        
    def update_filters(self, provinces, types):
        """Update filter dropdowns"""
        # Province filter
        self.province_dropdown['values'] = ["All Provinces"] + sorted(provinces)
        
        # Type filter
        self.type_dropdown['values'] = ["All Types"] + sorted(types)
        
    def update_statutes_list(self):
        """Update the statutes treeview"""
        # Clear existing items
        for item in self.statutes_tree.get_children():
            self.statutes_tree.delete(item)
            
        # Apply filters
        self.filtered_statutes = self.filter_statutes()
        
        # Add items to treeview
        for i, statute in enumerate(self.filtered_statutes):
            # Create status indicators
            status_indicators = []
            if statute.get("_has_missing_date", False):
                status_indicators.append("📅")
            if statute.get("_has_missing_name", False):
                status_indicators.append("📝")
            
            status_text = " ".join(status_indicators) if status_indicators else "✓"
            
            # Truncate name for display
            name = statute.get("Statute_Name", "Unknown")
            if len(name) > 40:
                name = name[:37] + "..."
            
            # Insert into treeview with index as tag
            self.statutes_tree.insert("", "end", 
                                    text=status_text,
                                    values=(name, 
                                           statute.get("_group_province", "Unknown"),
                                           statute.get("_group_statute_type", "Unknown")),
                                    tags=(str(i),))  # Store index as tag
        
    def filter_statutes(self):
        """Filter statutes using NumPy for efficiency"""
        if not self.all_statutes or self.statute_names_array is None:
            return []
            
        # Start with all indices
        indices = np.arange(len(self.all_statutes))
        
        # Missing date filter
        if self.missing_date_var.get():
            indices = indices[self.missing_dates_mask[indices]]
            
        # Missing name filter
        if self.missing_name_var.get():
            indices = indices[self.missing_names_mask[indices]]
            
        # Search filter with fuzzy matching
        search_text = self.search_var.get().strip()
        if search_text:
            # Get statute names for the current filtered indices
            current_names = self.statute_names_array[indices]
            
            # Perform fuzzy matching
            matches = process.extract(
                search_text,
                current_names,
                scorer=fuzz.WRatio,
                limit=len(current_names)
            )
            
            # Filter by similarity score (threshold: 50)
            matched_indices = [i for i, (name, score) in enumerate(matches) if score > 50]
            indices = indices[matched_indices]
            
        # Province filter
        province_filter = self.province_var.get()
        if province_filter != "All Provinces":
            province_mask = self.provinces_array[indices] == province_filter
            indices = indices[province_mask]
            
        # Type filter
        type_filter = self.type_var.get()
        if type_filter != "All Types":
            type_mask = self.types_array[indices] == type_filter
            indices = indices[type_mask]
            
        # Return filtered statutes
        return [self.all_statutes[i] for i in indices]
        
    def on_search(self):
        """Handle search input"""
        self.update_statutes_list()
        
    def on_filter_change(self):
        """Handle filter changes"""
        self.update_statutes_list()
        
    def on_statute_select(self, event):
        """Handle statute selection"""
        selection = self.statutes_tree.selection()
        if not selection:
            return
            
        # Get the selected item
        item = selection[0]
        index_str = self.statutes_tree.item(item, "tags")[0]  # Get index from tags
        
        try:
            index = int(index_str)
            if 0 <= index < len(self.filtered_statutes):
                statute = self.filtered_statutes[index]
                self.current_statute = statute
                self.update_statute_display(statute)
                print(f"DEBUG: Selected statute: {statute.get('Statute_Name', 'Unknown')}")
            else:
                print(f"DEBUG: Invalid index: {index}")
        except (ValueError, IndexError) as e:
            print(f"DEBUG: Error getting statute: {e}")
        
    def update_statute_display(self, statute):
        """Update the statute display"""
        print(f"DEBUG: Updating display for statute: {statute.get('Statute_Name', 'Unknown')}")
        
        # Update name entry
        self.name_var.set(statute.get("Statute_Name", ""))
        
        # Update date entry
        self.date_var.set(statute.get("Date", ""))
        
        # Update statute info
        province = statute.get("_group_province", "Unknown")
        statute_type = statute.get("_group_statute_type", "Unknown")
        base_name = statute.get("_group_base_name", "Unknown")
        
        info_text = f"Province: {province} | Type: {statute_type} | Base: {base_name}"
        self.statute_info_label.config(text=info_text)
        
        # Update sections
        self.update_sections_display(statute)
        
    def update_sections_display(self, statute):
        """Update the sections display"""
        sections = statute.get("Sections", [])
        print(f"DEBUG: Found {len(sections)} sections for statute")
        
        # Clear section dropdown and text
        self.section_dropdown['values'] = []
        self.section_var.set("")
        self.sections_text.delete(1.0, tk.END)
        
        if not sections:
            self.sections_text.insert(tk.END, "No sections found")
            return
            
        # Populate section dropdown
        section_names = []
        for section in sections:
            name = section.get("Section", "").strip()
            if name:
                section_names.append(name)
        
        print(f"DEBUG: Section names: {section_names[:3]}...")  # Show first 3 section names
        
        self.section_dropdown['values'] = section_names
        if section_names:
            self.section_dropdown.current(0)
            self.on_section_select()
            
    def on_section_select(self, event=None):
        """Handle section selection"""
        if not self.current_statute:
            return
            
        selected_section = self.section_var.get()
        if not selected_section:
            return
            
        # Find the selected section
        sections = self.current_statute.get("Sections", [])
        for section in sections:
            if section.get("Section", "").strip() == selected_section:
                section_text = section.get("Statute", "No text available")
                self.sections_text.delete(1.0, tk.END)
                self.sections_text.insert(tk.END, section_text)
                break
                
    def save_date(self):
        """Save the date for the current statute"""
        if not self.current_statute:
            messagebox.showwarning("Warning", "No statute selected")
            return
            
        date_text = self.date_var.get().strip()
        if not date_text:
            messagebox.showwarning("Warning", "Please enter a date")
            return
            
        # Validate date format
        if not self.validate_date(date_text):
            messagebox.showerror("Error", "Invalid date format. Use YYYY-MM-DD")
            return
            
        try:
            # Update in database
            group_id = self.current_statute["_group_id"]
            statute_id = self.current_statute["_id"]
            
            # Find and update the specific statute in the group
            result = self.col.update_one(
                {"_id": group_id, "statutes._id": statute_id},
                {"$set": {"statutes.$.Date": date_text}}
            )
            
            if result.modified_count > 0:
                messagebox.showinfo("Success", f"Date saved: {date_text}")
                # Refresh data to update statistics
                self.load_data()
            else:
                messagebox.showerror("Error", "Failed to save date")
                
        except Exception as e:
            messagebox.showerror("Error", f"Error saving date: {e}")
            
    def save_name(self):
        """Save the name for the current statute"""
        if not self.current_statute:
            messagebox.showwarning("Warning", "No statute selected")
            return
            
        name_text = self.name_var.get().strip()
        if not name_text:
            messagebox.showwarning("Warning", "Please enter a name")
            return
            
        try:
            # Update in database
            group_id = self.current_statute["_group_id"]
            statute_id = self.current_statute["_id"]
            
            # Find and update the specific statute in the group
            result = self.col.update_one(
                {"_id": group_id, "statutes._id": statute_id},
                {"$set": {"statutes.$.Statute_Name": name_text}}
            )
            
            if result.modified_count > 0:
                messagebox.showinfo("Success", f"Name saved: {name_text}")
                # Refresh data to update statistics
                self.load_data()
            else:
                messagebox.showerror("Error", "Failed to save name")
                
        except Exception as e:
            messagebox.showerror("Error", f"Error saving name: {e}")
            
    def delete_statute(self):
        """Delete the currently selected statute"""
        if not self.current_statute:
            messagebox.showwarning("Warning", "No statute selected")
            return
            
        # Get statute details for confirmation
        statute_name = self.current_statute.get("Statute_Name", "Unknown")
        statute_date = self.current_statute.get("Date", "No date")
        
        # Ask for confirmation
        confirm = messagebox.askyesno(
            "Confirm Deletion", 
            f"Are you sure you want to delete this statute?\n\n"
            f"Name: {statute_name}\n"
            f"Date: {statute_date}\n\n"
            f"This action cannot be undone."
        )
        
        if not confirm:
            return
            
        try:
            # Get group and statute IDs
            group_id = self.current_statute["_group_id"]
            statute_id = self.current_statute["_id"]
            
            # Remove the statute from the group's statutes array
            result = self.col.update_one(
                {"_id": group_id},
                {"$pull": {"statutes": {"_id": statute_id}}}
            )
            
            if result.modified_count > 0:
                messagebox.showinfo("Success", f"Statute '{statute_name}' has been deleted")
                
                # Clear current statute display
                self.current_statute = None
                self.name_var.set("")
                self.date_var.set("")
                self.statute_info_label.config(text="Select a statute to view details")
                self.section_var.set("")
                self.section_dropdown['values'] = []
                self.sections_text.delete(1.0, tk.END)
                
                # Refresh data to update statistics and list
                self.load_data()
            else:
                messagebox.showerror("Error", "Failed to delete statute")
                
        except Exception as e:
            messagebox.showerror("Error", f"Error deleting statute: {e}")
            
    def validate_date(self, date_text):
        """Validate date format"""
        try:
            datetime.strptime(date_text, "%Y-%m-%d")
            return True
        except ValueError:
            return False
            
    def run(self):
        """Run the application"""
        self.root.mainloop()

def main():
    """Main function"""
    app = MissingDatesGUI()
    app.run()

if __name__ == "__main__":
    main() 