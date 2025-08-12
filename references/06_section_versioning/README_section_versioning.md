# Section Versioning Pipeline

This directory contains three scripts for managing statute sections after statute-level grouping and versioning is completed.

## 📋 Overview

The section versioning pipeline processes grouped statutes to:
1. **Split sections** from grouped statute documents
2. **Assign versions** to sections using semantic similarity
3. **Export section versions** in the required JSON format

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r 06_section_versioning/requirements.txt
```

### 2. Run the Pipeline

```bash
# Step 1: Split sections from grouped statutes
python 06_section_versioning/split_sections.py

# Step 2: Assign versions to sections
python 06_section_versioning/assign_section_versions.py

# Step 3: Export section versions
python 06_section_versioning/export_section_versions.py
```

## 📁 Scripts Overview

### 1. `split_sections.py`

**Purpose:** Extracts individual sections from grouped statute documents.

**Input:** `Statute-Grouped.statute_group` database
**Output:** `Statute-Sections.section` database

**Features:**
- Extracts sections from all versions of grouped statutes
- Preserves all section metadata (Section, Definition, Statute text)
- Maintains version information and group relationships
- Creates clean section documents for further processing

**Database Structure:**
```json
{
  "section_number": "6",
  "definition": "High Treason",
  "statute_text": "Section 6 of Constitution...",
  "base_statute_name": "Constitution of Pakistan",
  "version_id": "v1",
  "version_label": "Original",
  "version_date": "14-Aug-1973",
  "province": "Federal",
  "statute_type": "Constitution"
}
```

### 2. `assign_section_versions.py`

**Purpose:** Groups similar sections and assigns version timelines with active/inactive status.

**Input:** `Statute-Sections.section` database
**Output:** `Statute-Section-Versions.section_version` database

**Features:**
- Uses semantic similarity to identify same sections across versions
- Handles ordinance expiration rules (6+ months = inactive)
- Creates version timelines for each section
- Assigns `isActive` status based on latest valid version

**Similarity Detection:**
- **Section Number Similarity:** 85% threshold
- **Definition Similarity:** 85% threshold  
- **Text Content Similarity:** 80% threshold
- Uses multiple algorithms: `difflib`, `fuzzywuzzy`

**Ordinance Expiration Rules:**
- If version is latest and not expired → `"isActive": true`
- If version is older or expired (6+ months) → `"isActive": false`

**Database Structure:**
```json
{
  "Base_Statute_Name": "Constitution of Pakistan",
  "Province": "Federal",
  "Statute_Type": "Constitution",
  "Section": "6",
  "Definition": "High Treason",
  "Versions": [
    {
      "Version_ID": "v1",
      "Year": 1973,
      "Promulgation_Date": "14-Aug-1973",
      "Status": "Original",
      "Statute": "Section 6 of Constitution...",
      "isActive": false
    },
    {
      "Version_ID": "v2", 
      "Year": 2009,
      "Promulgation_Date": "31-Jul-2009",
      "Status": "Amendment",
      "Statute": "Section 6 of Constitution (18th Amendment)...",
      "isActive": true
    }
  ]
}
```

### 3. `export_section_versions.py`

**Purpose:** Exports section versions to JSON files in the required schema format.

**Input:** `Statute-Section-Versions.section_version` database
**Output:** JSON files in `06_section_versioning/exports/`

**Features:**
- Exports to multiple formats (sample, by province, all)
- Maintains required schema structure
- Creates organized output files
- Generates export summaries

**Output Files:**
- `sample_section_versions.json` - First 10 sections for testing
- `section_versions_Federal.json` - Sections by province
- `all_section_versions.json` - Complete export
- `export_summary.json` - Processing statistics

**Required Schema:**
```json
{
  "Base_Statute_Name": "Constitution of Pakistan",
  "Province": "Federal", 
  "Statute_Type": "Constitution",
  "Section_Versions": [
    {
      "Section": "6",
      "Definition": "High Treason",
      "Versions": [
        {
          "Version_ID": "v1",
          "Year": 1973,
          "Promulgation_Date": "14-Aug-1973",
          "Status": "Original",
          "Statute": "Section 6 of Constitution...",
          "isActive": false
        }
      ]
    }
  ]
}
```

## ⚙️ Configuration

### Similarity Thresholds

Edit `assign_section_versions.py` to adjust similarity thresholds:

```python
SIMILARITY_THRESHOLD = 0.85  # For section numbers and definitions
TEXT_SIMILARITY_THRESHOLD = 0.80  # For text content
```

### Database Connections

All scripts use the same MongoDB connection:
```python
MONGO_URI = "mongodb://localhost:27017"
```

## 📊 Expected Outputs

### Step 1: Section Splitting
```
✅ Successfully processed 431 groups
📊 Total sections extracted: 2,847
📈 Average sections per group: 6.6
```

### Step 2: Version Assignment
```
✅ Successfully processed 431 base statutes
📊 Total section versions created: 2,847
```

### Step 3: Export
```
💾 Exported 2,847 section versions to all_section_versions.json
📊 Summary exported to export_summary.json
```

## 🔧 Troubleshooting

### Common Issues

1. **MongoDB Connection Error**
   ```bash
   # Ensure MongoDB is running
   mongod --dbpath /path/to/data
   ```

2. **Missing Dependencies**
   ```bash
   # Install fuzzywuzzy and dependencies
   pip install fuzzywuzzy python-Levenshtein
   ```

3. **Low Similarity Scores**
   - Adjust thresholds in `assign_section_versions.py`
   - Check section numbering consistency
   - Verify text normalization

4. **Ordinance Expiration Issues**
   - Check date parsing in `parse_date()` function
   - Verify ordinance identification logic
   - Review 6-month calculation

### Debug Mode

Enable debug logging in any script:
```python
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
```

## 📈 Performance Tips

1. **Indexes:** Scripts automatically create database indexes for better performance
2. **Batch Processing:** Large datasets are processed in batches
3. **Memory Management:** Uses generators and streaming where possible
4. **Progress Tracking:** All scripts show progress bars with `tqdm`

## 🔍 Monitoring

### Log Files
- `sections_split_summary.json` - Step 1 summary
- `section_versions_summary.json` - Step 2 summary  
- `export_summary.json` - Step 3 summary

### Database Collections
- `Statute-Sections.section` - Individual sections
- `Statute-Section-Versions.section_version` - Versioned sections

## 🎯 Use Cases

1. **Legal Research:** Track section changes over time
2. **Compliance:** Identify active vs inactive sections
3. **Analysis:** Compare section versions across amendments
4. **Export:** Generate clean JSON for external systems

## 📝 Notes

- All scripts are idempotent (safe to run multiple times)
- Database collections are cleared before processing
- Original data is preserved in source databases
- Scripts handle missing or invalid data gracefully
- Export files are created in `06_section_versioning/exports/` directory 