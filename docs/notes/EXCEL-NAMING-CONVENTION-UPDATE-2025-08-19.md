# Excel File Naming Convention Update - 2025-08-19

## Overview
Updated all Excel file generation in the backend to follow the unified naming convention established for the LawChronicle project.

## Unified Naming Convention for Excel Files
Pattern: `{operation}-{database}-{collection}-{date}.xlsx`

### Excel Operation Prefixes
- `search-` - Excel exports from search/analysis operations
- `export-` - Excel exports from data export operations
- `report-` - Excel reports generated from processing results

## Files Updated

### 1. Phase 4 Search - Missing Dates Export
**File:** `backend/app/api/v1/endpoints/phase4_search.py`
**Endpoint:** `/api/v1/phase4/search/export-missing-dates`

**Before:**
```python
filename = f"missing_dates_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"
```

**After:**
```python
# Use unified naming convention: {operation}-{database}-{collection}-{date}.xlsx
database_name = "date-enriched-batches"  # From the source database
collections_str = "-".join(request.collections) if request.collections else "all"
date_str = datetime.utcnow().strftime('%Y-%m-%d')
filename = f"search-missing-dates-{database_name}-{collections_str}-{date_str}.xlsx"
```

**Examples:**
- Single collection: `search-missing-dates-date-enriched-batches-batch_1-2025-08-19.xlsx`
- Multiple collections: `search-missing-dates-date-enriched-batches-batch_1-batch_2-2025-08-19.xlsx`
- All collections: `search-missing-dates-date-enriched-batches-all-2025-08-19.xlsx`

### 2. Phase 4 - Date Processing Results Export
**File:** `backend/app/api/v1/endpoints/phase4.py`
**Endpoint:** `/api/v1/phase4/export-results`

**Before:**
```python
filename = f"phase4_date_processed_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
```

**After:**
```python
# Use unified naming convention: {operation}-{database}-{collection}-{date}.xlsx
date_str = datetime.now().strftime('%Y-%m-%d')
filename = f"export-date-processed-results-{date_str}.xlsx"
```

**Example:**
- `export-date-processed-results-2025-08-19.xlsx`

## Benefits of Unified Excel Naming

1. **Consistency**: All Excel exports follow the same pattern as metadata and other generated files
2. **Predictability**: Users can expect consistent naming across all file types
3. **Organization**: Files sort logically by operation type and date
4. **Searchability**: Standardized patterns make files easier to find
5. **Automation**: Scripts can easily match and process files using glob patterns

## File Discovery Support

The existing file discovery utilities in the frontend already support flexible matching patterns and will work with the new Excel naming convention without modification.

## Transition Period

During the transition period, both old and new Excel filename patterns may exist. The file organization utilities can handle both patterns gracefully.

## Future Excel File Generation

All new Excel file generation should follow this unified naming convention:
- Use operation prefixes: `search-`, `export-`, `report-`
- Include relevant database/collection context
- Use YYYY-MM-DD date format
- Use lowercase with hyphens as separators

## Related Documentation
- `BACKEND-METADATA-NAMING-UPDATE-2025-08-19.md` - Backend metadata naming updates
- `FILE-ORGANIZATION-COMPLETE-2025-08-19.md` - Original file organization implementation
