import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QListWidget, QLabel, QTextEdit, QMessageBox, QCheckBox, QComboBox, QPushButton, QGroupBox, QGridLayout
)
from PyQt5.QtCore import Qt
from pymongo import MongoClient
from rapidfuzz import process, fuzz

# --- MongoDB Config ---
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "Statutes"
COLL_NAME = "normalized_statutes"

class StatuteExplorer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Statute Explorer")
        self.resize(900, 600)
        self.section_name_dict = {}  # Will hold all unique section names and their counts
        self.init_db()
        self.init_ui()
        self.load_databases()
        self.load_statute_names()

    def init_db(self):
        try:
            self.client = MongoClient(MONGO_URI)
            self.db = self.client[DB_NAME]
            self.col = self.db[COLL_NAME]
            print(f"Connected to {DB_NAME}.{COLL_NAME}")
        except Exception as e:
            QMessageBox.critical(self, "DB Error", f"Could not connect to MongoDB: {e}")
            sys.exit(1)

    def init_ui(self):
        layout = QVBoxLayout()
        
        # Database Configuration Panel
        config_group = QGroupBox("Database Configuration")
        config_layout = QGridLayout()
        
        # Database dropdown
        config_layout.addWidget(QLabel("Database:"), 0, 0)
        self.db_dropdown = QComboBox()
        self.db_dropdown.currentTextChanged.connect(self.on_db_change)
        config_layout.addWidget(self.db_dropdown, 0, 1)
        
        # Collection dropdown
        config_layout.addWidget(QLabel("Collection:"), 0, 2)
        self.collection_dropdown = QComboBox()
        self.collection_dropdown.currentTextChanged.connect(self.on_collection_change)
        config_layout.addWidget(self.collection_dropdown, 0, 3)
        
        # Refresh button
        self.refresh_btn = QPushButton("Refresh Data")
        self.refresh_btn.clicked.connect(self.refresh_data)
        config_layout.addWidget(self.refresh_btn, 0, 4)
        
        # Connection status
        self.connection_status = QLabel("Connected")
        self.connection_status.setStyleSheet("color: green;")
        config_layout.addWidget(self.connection_status, 1, 0, 1, 5)
        
        config_group.setLayout(config_layout)
        layout.addWidget(config_group)
        
        # Search section
        search_layout = QHBoxLayout()
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search statute name...")
        self.search_bar.textChanged.connect(self.on_search)
        search_layout.addWidget(QLabel("Search:"))
        search_layout.addWidget(self.search_bar)
        layout.addLayout(search_layout)

        # Add checkbox for filtering statutes with empty date
        self.empty_date_checkbox = QCheckBox("Show only statutes with empty date")
        self.empty_date_checkbox.stateChanged.connect(self.on_search)
        layout.addWidget(self.empty_date_checkbox)

        self.results_list = QListWidget()
        self.results_list.currentRowChanged.connect(self.on_select)
        layout.addWidget(self.results_list)

        # Section dropdown
        section_layout = QHBoxLayout()
        section_label = QLabel("Section:")
        self.section_dropdown = QComboBox()
        self.section_dropdown.currentIndexChanged.connect(self.on_section_select)
        section_layout.addWidget(section_label)
        section_layout.addWidget(self.section_dropdown)
        layout.addLayout(section_layout)

        details_layout = QVBoxLayout()
        self.section_text_label = QLabel("<b>Section Text:</b>")
        self.section_text = QTextEdit()
        self.section_text.setReadOnly(True)
        self.date_label = QLabel("<b>Date:</b> ")
        details_layout.addWidget(self.section_text_label)
        details_layout.addWidget(self.section_text)
        details_layout.addWidget(self.date_label)
        layout.addLayout(details_layout)

        self.setLayout(layout)

    def load_databases(self):
        """Load available databases and collections"""
        try:
            # Get all databases
            databases = self.client.list_database_names()
            self.db_dropdown.clear()
            self.db_dropdown.addItems(databases)
            
            # Set current database
            current_db_index = self.db_dropdown.findText(DB_NAME)
            if current_db_index >= 0:
                self.db_dropdown.setCurrentIndex(current_db_index)
            else:
                self.db_dropdown.setCurrentIndex(0)
            
            self.load_collections()
            
        except Exception as e:
            QMessageBox.warning(self, "Warning", f"Could not load databases: {e}")

    def load_collections(self):
        """Load collections for the selected database"""
        try:
            current_db = self.db_dropdown.currentText()
            if current_db:
                db = self.client[current_db]
                collections = db.list_collection_names()
                self.collection_dropdown.clear()
                self.collection_dropdown.addItems(collections)
                
                # Set current collection
                current_col_index = self.collection_dropdown.findText(COLL_NAME)
                if current_col_index >= 0:
                    self.collection_dropdown.setCurrentIndex(current_col_index)
                else:
                    self.collection_dropdown.setCurrentIndex(0)
                    
        except Exception as e:
            QMessageBox.warning(self, "Warning", f"Could not load collections: {e}")

    def on_db_change(self, db_name):
        """Handle database change"""
        if db_name:
            self.load_collections()
            self.connection_status.setText(f"Connected to {db_name}")
            self.connection_status.setStyleSheet("color: green;")

    def on_collection_change(self, collection_name):
        """Handle collection change"""
        if collection_name:
            current_db = self.db_dropdown.currentText()
            self.connection_status.setText(f"Connected to {current_db}.{collection_name}")
            self.connection_status.setStyleSheet("color: green;")

    def refresh_data(self):
        """Refresh data from the selected database and collection"""
        try:
            current_db = self.db_dropdown.currentText()
            current_collection = self.collection_dropdown.currentText()
            
            if current_db and current_collection:
                self.db = self.client[current_db]
                self.col = self.db[current_collection]
                
                # Clear current data
                self.statutes = []
                self.statute_names = []
                self.filtered_indices = []
                self.section_name_dict = {}
                
                # Reload data
                self.load_statute_names()
                
                self.connection_status.setText(f"Connected to {current_db}.{current_collection} - Data refreshed")
                self.connection_status.setStyleSheet("color: green;")
                
                QMessageBox.information(self, "Success", f"Data refreshed from {current_db}.{current_collection}")
            else:
                QMessageBox.warning(self, "Warning", "Please select both database and collection")
                
        except Exception as e:
            self.connection_status.setText(f"Error: {str(e)}")
            self.connection_status.setStyleSheet("color: red;")
            QMessageBox.critical(self, "Error", f"Could not refresh data: {e}")

    def load_statute_names(self):
        # Load all statutes (name, _id) for fast search
        try:
            self.statutes = list(self.col.find({}, {"Statute_Name": 1, "Sections": 1, "Date": 1}))
            self.statute_names = [doc.get("Statute_Name", "") for doc in self.statutes]
            self.filtered_indices = list(range(len(self.statutes)))
            self.build_section_name_dict()
            self.update_results_list()
        except Exception as e:
            QMessageBox.warning(self, "Warning", f"Could not load statute names: {e}")

    def build_section_name_dict(self):
        # Build a dictionary of all unique section names (case-insensitive, stripped)
        self.section_name_dict = {}
        for doc in self.statutes:
            for section in doc.get("Sections", []):
                name = section.get("Section", "").strip()
                if name:
                    key = name.lower()
                    if key not in self.section_name_dict:
                        self.section_name_dict[key] = name  # Store original casing
        # Optionally, you could count occurrences if desired

    def on_search(self, text=None):
        # Accepts optional text argument for compatibility with both QLineEdit and QCheckBox signals
        search_text = self.search_bar.text()
        show_empty_date = self.empty_date_checkbox.isChecked()
        if not search_text.strip():
            indices = list(range(len(self.statutes)))
        else:
            matches = process.extract(
                search_text,
                self.statute_names,
                scorer=fuzz.WRatio,
                limit=20
            )
            indices = [i for i, score in [(self.statute_names.index(m[0]), m[1]) for m in matches] if score > 50]
        # Apply empty date filter
        if show_empty_date:
            self.filtered_indices = [i for i in indices if self.statutes[i].get("Date", "") == ""]
        else:
            self.filtered_indices = indices
        self.update_results_list()

    def update_results_list(self):
        self.results_list.clear()
        for i in self.filtered_indices:
            self.results_list.addItem(self.statute_names[i])
        if self.filtered_indices:
            self.results_list.setCurrentRow(0)
        else:
            self.section_dropdown.clear()
            self.section_text.clear()
            self.date_label.setText("<b>Date:</b> ")

    def on_select(self, row):
        if row < 0 or row >= len(self.filtered_indices):
            self.section_dropdown.clear()
            self.section_text.clear()
            self.date_label.setText("<b>Date:</b> ")
            return
        idx = self.filtered_indices[row]
        doc = self.statutes[idx]
        sections = doc.get("Sections", [])
        # Build a mapping of section name (original) -> section text for this statute
        self.current_section_map = {}
        section_names = []
        for section in sections:
            name = section.get("Section", "").strip()
            if name:
                section_names.append(name)
                self.current_section_map[name] = section.get("Statute", "(No text found)")
        # Populate dropdown
        self.section_dropdown.blockSignals(True)
        self.section_dropdown.clear()
        if section_names:
            self.section_dropdown.addItems(section_names)
            self.section_dropdown.setCurrentIndex(0)
            self.on_section_select(0)
        else:
            self.section_text.setText("(No sections found)")
        self.section_dropdown.blockSignals(False)
        date = doc.get("Date", "(No date found)")
        self.date_label.setText(f"<b>Date:</b> {date}")

    def on_section_select(self, index):
        if not hasattr(self, "current_section_map"):
            self.section_text.setText("(No section selected)")
            return
        section_name = self.section_dropdown.currentText()
        if section_name in self.current_section_map:
            self.section_text.setText(self.current_section_map[section_name])
        else:
            self.section_text.setText("(No text found)")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = StatuteExplorer()
    window.show()
    sys.exit(app.exec_()) 