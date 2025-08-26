import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QListWidget, QLabel, QTextEdit, QMessageBox, QCheckBox
)
from PyQt5.QtCore import Qt
from pymongo import MongoClient
from rapidfuzz import process, fuzz

# --- MongoDB Config ---
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "Batched-Statutes"
COLL_NAME = "batch10"

class StatuteExplorer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Statute Explorer")
        self.resize(800, 500)
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

        details_layout = QVBoxLayout()
        self.preamble_label = QLabel("<b>Preamble:</b>")
        self.preamble_text = QTextEdit()
        self.preamble_text.setReadOnly(True)
        self.date_label = QLabel("<b>Date:</b> ")
        details_layout.addWidget(self.preamble_label)
        details_layout.addWidget(self.preamble_text)
        details_layout.addWidget(self.date_label)
        layout.addLayout(details_layout)

        self.setLayout(layout)

    def load_statute_names(self):
        # Load all statutes (name, _id) for fast search
        self.statutes = list(self.col.find({}, {"Statute_Name": 1, "Sections": 1, "Date": 1}))
        self.statute_names = [doc.get("Statute_Name", "") for doc in self.statutes]
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
            self.preamble_text.clear()
            self.date_label.setText("<b>Date:</b> ")

    def on_select(self, row):
        if row < 0 or row >= len(self.filtered_indices):
            self.preamble_text.clear()
            self.date_label.setText("<b>Date:</b> ")
            return
        idx = self.filtered_indices[row]
        doc = self.statutes[idx]
        # --- Updated preamble extraction ---
        preamble = "(No preamble found)"
        sections = doc.get("Sections", [])
        for section in sections:
            if section.get("Section", "").strip().lower() == "preamble":
                preamble = section.get("Statute", "(No preamble found)")
                break
        date = doc.get("Date", "(No date found)")
        self.preamble_text.setText(preamble)
        self.date_label.setText(f"<b>Date:</b> {date}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = StatuteExplorer()
    window.show()
    sys.exit(app.exec_()) 