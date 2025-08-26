# Backend Metadata Naming Convention Update
*Updated: August 19, 2025*

## Overview
Updated all backend services to use the unified naming convention for metadata files generated from the frontend interface.

## Changes Made

### 1. Normalization Service (`normalization_service.py`)
**Before:**
```python
filename = f"metadata_{actual_db}_{source_collection}_to_{target_collection}_{timestamp}.json"
# Example: metadata_Legislation_raw_statutes_to_normalized_statutes_2025-08-19_15-32-45.json
```

**After:**
```python
operation = "normalize"
database = actual_db.lower().replace("_", "-")
collection = source_collection.lower().replace("_", "-")
filename = f"{operation}-{database}-{collection}-{date_str}.json"
# Example: normalize-legislation-raw-statutes-2025-08-19.json
```

### 2. Phase 4 Service (`phase4_service.py`)
**Before:**
```python
filename = f"metadata_{target_collection_name}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
# Example: metadata_batch1_enriched_20250819_153245.json
```

**After:**
```python
operation = "merge"
collection = target_collection_name.lower().replace("_", "-")
filename = f"{operation}-date-enriched-{collection}-{date_str}.json"
# Example: merge-date-enriched-batch1-2025-08-19.json
```

### 3. Phase 3 Endpoints (`phase3.py`)

#### Section Splitting
**Before:**
```python
meta_filename = f"metadata_split_{target_database}_{target_prefix}_{date.today().isoformat()}.json"
```

**After:**
```python
operation = "split"
database = target_database.lower().replace("_", "-")
collection = target_prefix.lower().replace("_", "-")
meta_filename = f"{operation}-{database}-{collection}-{date_str}.json"
```

#### Field Cleaning
**Before:**
```python
meta_filename = f"metadata_clean_{config.target_database}_{config.target_collection_prefix}_{batch_suffix}_{date.today().isoformat()}.json"
```

**After:**
```python
operation = "cleaning"
database = config.target_database.lower().replace("_", "-")
collection = config.target_collection_prefix.lower().replace("_", "-")
meta_filename = f"{operation}-{database}-{collection}-{batch_suffix}-{date_str}.json"
```

#### Metadata Generation
**Before:**
```python
meta_filename = f"metadata_generated_{config.target_database}_{config.target_collection_prefix}_{date.today().isoformat()}.json"
```

**After:**
```python
operation = "generated"
database = config.target_database.lower().replace("_", "-")
collection = config.target_collection_prefix.lower().replace("_", "-")
meta_filename = f"{operation}-{database}-{collection}-{date_str}.json"
```

#### Operation Metadata
**Before:**
```python
meta_filename = f"metadata_{operation_type}_{target_db}_{coll_part}_{date.today().isoformat()}.json"
```

**After:**
```python
database = target_db.lower().replace("_", "-")
collection = coll_part.lower().replace("_", "-")
meta_filename = f"{operation_type}-{database}-{collection}-{date_str}.json"
```

#### Pakistan Validation
**Before:**
```python
meta_filename = f"metadata_pakistan_validation_{operation_type}_{config.target_database}_{config.target_collection_prefix}_{batch_suffix}_{date.today().isoformat()}.json"
```

**After:**
```python
operation_type = "dry-run" if dry_run else "validation"
database = config.target_database.lower().replace("_", "-")
collection = config.target_collection_prefix.lower().replace("_", "-")
meta_filename = f"pakistan-{operation_type}-{database}-{collection}-{batch_suffix}-{date_str}.json"
```

### 4. Metadata File Discovery
Updated file discovery to support both old and new naming conventions during transition:

**Before:**
```python
files = glob.glob(os.path.join(metadata_dir, "metadata_*.json"))
```

**After:**
```python
files = glob.glob(os.path.join(metadata_dir, "*.json"))
# Filter for metadata files (both old and new naming conventions)
metadata_files = [f for f in files if (
    os.path.basename(f).startswith("metadata_") or  # Old convention
    any(os.path.basename(f).startswith(prefix) for prefix in ["split-", "cleaning-", "generated-", "pakistan-", "normalize-", "merge-"])  # New convention
)]
```

## Unified Naming Convention Applied

### Pattern
```
{operation}-{database}-{collection}-{date}.{ext}
```

### Operation Prefixes
- `normalize` - Database normalization operations
- `merge` - Date enrichment merging operations  
- `split` - Section splitting operations
- `cleaning` - Field cleaning operations
- `generated` - Generated metadata summaries
- `pakistan` - Pakistan-specific validation operations

### Examples
- `normalize-legislation-raw-statutes-2025-08-19.json`
- `merge-date-enriched-batch1-2025-08-19.json`
- `split-gilgit-baltistan-sections-2025-08-19.json`
- `cleaning-batched-statutes-all-batches-2025-08-19.json`
- `pakistan-validation-cleaned-batches-batch1-2025-08-19.json`

## Frontend Impact
When users click "Generate Metadata" in the frontend, the backend will now create files with the new unified naming convention. The changes are:

1. **Consistent date format**: YYYY-MM-DD (no timestamps with seconds)
2. **Hyphens instead of underscores**: Better readability and web compatibility
3. **Descriptive operation prefixes**: Clear purpose identification
4. **Lowercase normalization**: Database and collection names are normalized to lowercase with hyphens

## Backward Compatibility
- File discovery updated to find both old and new naming conventions
- Existing old metadata files remain functional
- New files will use the unified convention
- No breaking changes to existing functionality

## Benefits
1. **Consistency**: All metadata files now follow the same pattern
2. **Readability**: Hyphens make names more readable than underscores
3. **Organization**: Operation prefixes make file purposes clear
4. **Maintainability**: Unified patterns easier to manage and automate
5. **Professional standards**: Follows modern file naming best practices

---
*These changes ensure that metadata generated from the frontend interface will follow the same unified naming convention applied to the rest of the repository files.*
