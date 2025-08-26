import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QListWidget, QLabel, QTextEdit, QMessageBox, QCheckBox, QComboBox
)
from PyQt5.QtCore import Qt
from pymongo import MongoClient
from rapidfuzz import process, fuzz

# --- MongoDB Config ---
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "Final-Batched-Statutes"  # Updated for versioned database
COLL_NAME = "batch1"  # Updated collection name

class StatuteExplorer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Statute Explorer (Versioned)")
        self.resize(800, 600)
        self.init_db()
        self.init_ui()
        self.load_statute_names()

    def init_db(self):
        try:
            self.client = MongoClient(MONGO_URI)
            self.db = self.client[DB_NAME]
            self.col = self.db[COLL_NAME]
        except Exception as e:
            QMessageBox.critical(self, "DB Error", f"Could not connect to MongoDB: {e}")
            sys.exit(1)

    def init_ui(self):
        layout = QVBoxLayout()
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

        # Section selection
        section_layout = QHBoxLayout()
        section_label = QLabel("Section:")
        self.section_dropdown = QComboBox()
        self.section_dropdown.currentIndexChanged.connect(self.on_section_select)
        section_layout.addWidget(section_label)
        section_layout.addWidget(self.section_dropdown)
        layout.addLayout(section_layout)

        # Version selection
        version_layout = QHBoxLayout()
        version_label = QLabel("Version:")
        self.version_dropdown = QComboBox()
        self.version_dropdown.currentIndexChanged.connect(self.on_version_select)
        version_layout.addWidget(version_label)
        version_layout.addWidget(self.version_dropdown)
        layout.addLayout(version_layout)

        # Version details
        self.version_details_label = QLabel("<b>Version Details:</b> ")
        layout.addWidget(self.version_details_label)

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

    def load_statute_names(self):
        # Load all statutes for versioned database
        self.statutes = list(self.col.find({}, {
            "base_statute_name": 1, 
            "Section_Versions": 1, 
            "latest_version_date": 1
        }))
        self.statute_names = [doc.get("base_statute_name", "") for doc in self.statutes]
        self.filtered_indices = list(range(len(self.statutes)))
        self.update_results_list()

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
            self.filtered_indices = [i for i in indices if not self.statutes[i].get("latest_version_date")]
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
            self.version_dropdown.clear()
            self.section_text.clear()
            self.date_label.setText("<b>Date:</b> ")
            self.version_details_label.setText("<b>Version Details:</b> ")

    def on_select(self, row):
        if row < 0 or row >= len(self.filtered_indices):
            self.section_dropdown.clear()
            self.version_dropdown.clear()
            self.section_text.clear()
            self.date_label.setText("<b>Date:</b> ")
            self.version_details_label.setText("<b>Version Details:</b> ")
            return
        
        idx = self.filtered_indices[row]
        doc = self.statutes[idx]
        
        # Store all section versions for this statute
        self.current_section_versions = doc.get("Section_Versions", [])
        
        # Populate section dropdown
        self.section_dropdown.blockSignals(True)
        self.section_dropdown.clear()
        if self.current_section_versions:
            for section in self.current_section_versions:
                section_name = section.get("Section", "Unknown")
                definition = section.get("Definition", "")
                display_text = f"{section_name}: {definition}" if definition else section_name
                self.section_dropdown.addItem(display_text, section)
            self.section_dropdown.setCurrentIndex(0)
            self.on_section_select(0)
        else:
            self.section_text.setText("(No sections found)")
            self.version_details_label.setText("<b>Version Details:</b> No sections available")
        self.section_dropdown.blockSignals(False)
        
        # Show latest version date
        date = doc.get("latest_version_date", "(No date found)")
        if date and isinstance(date, str):
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(date.replace('Z', '+00:00'))
                date = dt.strftime("%d-%b-%Y")
            except:
                pass
        self.date_label.setText(f"<b>Latest Version Date:</b> {date}")

    def on_section_select(self, index):
        if not hasattr(self, 'current_section_versions') or not self.current_section_versions:
            return
        
        if index >= 0 and index < len(self.current_section_versions):
            section = self.current_section_versions[index]
            self.current_versions = section.get("Versions", [])
            
            # Populate version dropdown
            self.version_dropdown.blockSignals(True)
            self.version_dropdown.clear()
            if self.current_versions:
                for version in self.current_versions:
                    version_id = version.get("Version_ID", "Unknown")
                    year = version.get("Year", "")
                    promulgation_date = version.get("Promulgation_Date", "")
                    status = version.get("Status", "")
                    display_text = f"{version_id} ({year}) - {promulgation_date} - {status}"
                    self.version_dropdown.addItem(display_text, version)
                self.version_dropdown.setCurrentIndex(0)
                self.on_version_select(0)
            else:
                self.section_text.setText("(No versions found)")
                self.version_details_label.setText("<b>Version Details:</b> No versions available")
            self.version_dropdown.blockSignals(False)

    def on_version_select(self, index):
        if not hasattr(self, 'current_versions') or not self.current_versions:
            return
        
        if index >= 0 and index < len(self.current_versions):
            version = self.current_versions[index]
            
            # Display version details
            version_id = version.get("Version_ID", "Unknown")
            year = version.get("Year", "")
            promulgation_date = version.get("Promulgation_Date", "")
            status = version.get("Status", "")
            is_active = version.get("isActive", False)
            
            details_text = f"<b>Version Details:</b> ID: {version_id}, Year: {year}, Date: {promulgation_date}, Status: {status}, Active: {is_active}"
            self.version_details_label.setText(details_text)
            
            # Display section text
            section_text = version.get("Statute", "(No text found)")
            self.section_text.setText(section_text)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = StatuteExplorer()
    window.show()
    sys.exit(app.exec_()) 