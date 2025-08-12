# Legal Statute Versioning Pipeline

This module provides a comprehensive solution for cleaning, grouping, and versioning legal statutes stored in MongoDB. The pipeline consists of three modular scripts that work together to create a clean, structured dataset with proper versioning.

## 📋 Overview

The versioning pipeline processes legal statutes through three stages:

1. **Duplicate Removal** - Identifies and removes duplicate statutes
2. **Base Grouping** - Groups statutes by their base names
3. **Version Assignment** - Assigns chronological version labels

## 🏗️ Architecture

```
Statute-Batch-1 (MongoDB)
    ↓
Script 1: remove_duplicates.py
    ↓
Script 2: group_statutes_by_base.py
    ↓
Script 3: assign_statute_versions.py
    ↓
Versioned Statutes (MongoDB + JSON)
```

## 📁 Files

### Core Scripts
- `remove_duplicates.py` - Removes duplicate statutes based on name and content similarity
- `group_statutes_by_base.py` - Groups statutes by base names after removing legal suffixes
- `assign_statute_versions.py` - Assigns version labels chronologically

### Output Files
- `duplicate_removal_log.json` - Detailed log of removed duplicates
- `grouped_statutes.json` - Statute groupings by base name
- `versioned_statutes.json` - Final versioning information

## 🚀 Usage

### Step 1: Remove Duplicates

```bash
python 05_statute_versioning/remove_duplicates.py
```

**What it does:**
- Normalizes statute names (lowercase, remove punctuation)
- Extracts content from all sections and fields
- Uses difflib for content similarity comparison
- Retains most recent version based on Date field
- Removes exact and near-duplicate statutes

**Output:**
- Removes duplicate statutes from database
- Creates `duplicate_removal_log.json` with details

### Step 2: Group by Base Name

```bash
python 05_statute_versioning/group_statutes_by_base.py
```

**What it does:**
- Removes legal suffixes (Act, Ordinance, Law, Rule, etc.)
- Removes parenthetical expressions like "(Amendment)"
- Creates `base_name` field for each statute
- Groups statutes by normalized base names
- Merges similar groups using similarity threshold

**Output:**
- Updates database with `base_name` field
- Creates `grouped_statutes.json` with groupings

### Step 3: Assign Versions

```bash
python 05_statute_versioning/assign_statute_versions.py
```

**What it does:**
- Sorts statutes chronologically by Date field
- Assigns version labels: "Original", "First Amendment", "Second Amendment", etc.
- Handles missing or invalid dates
- Updates database with `Version_Label` field

**Output:**
- Updates database with `Version_Label` field
- Creates `versioned_statutes.json` with versioning info

### Step 4: Restructure to Groups (Optional)

```bash
python 05_statute_versioning/restructure_to_groups.py
```

**What it does:**
- Creates new database `Statute-Grouped` with grouped structure
- Each group contains all versions of a statute under one document
- Maintains chronological order within groups
- Preserves all original data in hierarchical structure

**Output:**
- New database: `Statute-Grouped.statute_group`
- Creates `grouped_database_structure.json` for reference

## ⚙️ Configuration

### Database Settings
```python
MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "Statute-Batch-1"
COLL_NAME = "statute"
```

### Similarity Thresholds
```python
CONTENT_SIMILARITY_THRESHOLD = 0.85  # For duplicate detection
NAME_SIMILARITY_THRESHOLD = 0.9       # For name matching
SIMILARITY_THRESHOLD = 0.8            # For group merging
```

## 📊 Schema Changes

The scripts add the following fields to your statute documents:

### New Fields
- `base_name` - Normalized base name without legal suffixes
- `Version_Label` - Chronological version label

### Example Document
```json
{
  "_id": "...",
  "Statute_Name": "Anti-Terrorism Act 1997",
  "Date": "1997-08-14",
  "Statute_Type": "Act",
  "Sections": [...],
  "base_name": "Anti-Terrorism",
  "Version_Label": "Original"
}
```

## 🔧 Features

### Script 1: Duplicate Removal
- ✅ **Content-based similarity** using difflib
- ✅ **Name normalization** with legal suffix removal
- ✅ **Date-based retention** (keeps most recent)
- ✅ **Configurable thresholds** for similarity matching
- ✅ **Detailed logging** of removed duplicates

### Script 2: Base Grouping
- ✅ **Legal suffix removal** (Act, Ordinance, Law, etc.)
- ✅ **Parenthetical expression removal** (Amendment, etc.)
- ✅ **Similarity-based merging** of similar groups
- ✅ **Database updates** with base_name field
- ✅ **JSON export** of groupings

### Script 3: Version Assignment
- ✅ **Chronological sorting** by Date field
- ✅ **Intelligent version labels** (Original, First Amendment, etc.)
- ✅ **Missing date handling** (places at end)
- ✅ **Database updates** with Version_Label field
- ✅ **Validation and statistics**

## 📈 Example Workflow

### Input Statutes
```
Anti-Terrorism Act 1997
Anti-Terrorism Act 1997 (Amendment)
Anti-Terrorism (Amendment) Act 2004
```

### After Script 1 (Duplicate Removal)
```
Anti-Terrorism Act 1997 (Amendment)  # Most recent kept
```

### After Script 2 (Base Grouping)
```
base_name: "Anti-Terrorism"
- Anti-Terrorism Act 1997 (Amendment)
- Anti-Terrorism (Amendment) Act 2004
```

### After Script 3 (Version Assignment)
```
base_name: "Anti-Terrorism"
- Original: Anti-Terrorism Act 1997 (Amendment)
- First Amendment: Anti-Terrorism (Amendment) Act 2004
```

## 🛠️ Dependencies

```bash
pip install pymongo tqdm python-dateutil
```

## 📊 Statistics

The scripts provide detailed statistics:

### Duplicate Removal
- Total statutes processed
- Statutes with preamble sections
- Statutes cleaned
- Total sections cleaned

### Base Grouping
- Total base groups
- Groups with multiple statutes
- Average statutes per group

### Version Assignment
- Total base groups
- Groups with multiple versions
- Version label distribution

## 🔍 Monitoring

### Log Files
- `duplicate_removal_log.json` - Details of removed duplicates
- `grouped_statutes.json` - Statute groupings
- `versioned_statutes.json` - Final versioning information

### Console Output
Each script provides detailed progress and statistics:
```
🚀 Starting duplicate removal process...
📊 Found 1500 statutes
📊 Found 45 duplicate groups
✅ Updated 1200 statutes with base_name field
📊 After merging: 800 base groups
✅ Statute versioning completed!
```

## ⚠️ Important Notes

1. **Backup your data** before running the scripts
2. **Run scripts in order** (1 → 2 → 3)
3. **Check logs** for any issues or warnings
4. **Validate results** using the provided statistics
5. **Adjust thresholds** if needed for your specific data

## 🐛 Troubleshooting

### Common Issues

**Script 1 fails:**
- Check MongoDB connection
- Verify database and collection names
- Ensure statutes have Date fields

**Script 2 creates too many groups:**
- Lower `SIMILARITY_THRESHOLD` for more aggressive merging
- Check for inconsistent naming patterns

**Script 3 assigns wrong versions:**
- Verify Date field format
- Check for missing or invalid dates
- Review chronological ordering

### Validation Commands

```bash
# Check database connection
python -c "from pymongo import MongoClient; client = MongoClient('mongodb://localhost:27017'); print(client.list_database_names())"

# Verify script outputs
ls -la 05_statute_versioning/*.json

# Check database updates
python -c "from pymongo import MongoClient; client = MongoClient('mongodb://localhost:27017'); col = client['Statute-Batch-1']['statute']; print(col.count_documents({'base_name': {'$exists': True}}))"
```

## 📝 License

This module is part of the LawChronicle project for legal data processing and versioning. 