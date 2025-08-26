# Phase 2 API Documentation - New Endpoints

## Overview
This document describes the new sorting and cleaning endpoints added to the Phase 2 API for the LawChronicle project.

## Authentication
All endpoints require a Bearer token in the Authorization header:
```
Authorization: Bearer <token>
```

## Endpoints

### POST /api/v1/phase2/apply-sorting

Applies sorting rules to normalized statute documents, organizing sections within each statute according to specified rules.

**Request Body:**
```json
{
  "rules": {
    "preamble_first": true,
    "numeric_order": true,
    "alphabetical_fallback": true,
    "custom_sort_order": null
  },
  "scope": "all",
  "target_collection": "sorted_statutes",
  "database_name": "Statutes"
}
```

**Request Fields:**
- `rules` (required): Sorting configuration object
  - `preamble_first` (boolean): Whether preamble sections should be sorted first
  - `numeric_order` (boolean): Whether numeric sections should be sorted by value
  - `alphabetical_fallback` (boolean): Whether text sections should be sorted alphabetically
  - `custom_sort_order` (object, optional): Custom ordering for specific sections
- `scope` (optional): Scope of operation, defaults to "all"
- `target_collection` (optional): Target collection name, defaults to "sorted_statutes"
- `database_name` (optional): Database name, defaults to configured database

**Response:**
```json
{
  "success": true,
  "message": "Sorting applied successfully to 150 documents",
  "changes_count": 45,
  "total_documents": 150,
  "sample_changes": [
    {
      "statute_name": "Sample Statute A",
      "original_order": ["3", "preamble", "1", "2"],
      "new_order": ["preamble", "1", "2", "3"],
      "sections_affected": 4
    }
  ],
  "target_collection": "sorted_statutes",
  "applied_at": "2025-08-14T20:30:00.000Z"
}
```

**Status Codes:**
- `200`: Success - Sorting applied successfully
- `422`: Validation Error - Invalid request format
- `500`: Server Error - Database or processing error

### POST /api/v1/phase2/apply-cleaning

Applies field mapping and cleaning rules to normalized statute documents, transforming field names and content according to specified mappings.

**Request Body:**
```json
{
  "mappings": [
    {
      "source": "number",
      "target": "section_number",
      "enabled": true
    },
    {
      "source": "definition", 
      "target": "section_content",
      "enabled": true
    },
    {
      "source": "content",
      "target": "section_text",
      "enabled": false
    }
  ],
  "scope": "all",
  "target_collection": "cleaned_statutes",
  "database_name": "Statutes"
}
```

**Request Fields:**
- `mappings` (required): Array of field mapping objects
  - `source` (string): Source field name to map from
  - `target` (string): Target field name to map to
  - `enabled` (boolean): Whether this mapping should be applied
- `scope` (optional): Scope of operation, defaults to "all"
- `target_collection` (optional): Target collection name, defaults to "cleaned_statutes"
- `database_name` (optional): Database name, defaults to configured database

**Response:**
```json
{
  "success": true,
  "message": "Field cleaning applied successfully to 150 documents",
  "changes_count": 120,
  "total_documents": 150,
  "mappings_applied": 2,
  "sample_changes": [
    {
      "statute_name": "Sample Statute A",
      "sections_modified": 8,
      "field_changes": [
        {
          "field_mapping": "number → section_number",
          "value_preview": "1"
        },
        {
          "field_mapping": "definition → section_content", 
          "value_preview": "This section defines the basic principles..."
        }
      ]
    }
  ],
  "target_collection": "cleaned_statutes",
  "applied_at": "2025-08-14T20:35:00.000Z"
}
```

**Status Codes:**
- `200`: Success - Cleaning applied successfully
- `422`: Validation Error - Invalid request format or no enabled mappings
- `500`: Server Error - Database or processing error

## Data Models

### SortingRules
```python
class SortingRules(BaseModel):
    preamble_first: bool = True
    numeric_order: bool = True
    alphabetical_fallback: bool = True
    custom_sort_order: Optional[Dict[str, int]] = None
```

### FieldMapping
```python
class FieldMapping(BaseModel):
    source: str
    target: str
    enabled: bool = True
```

## Error Handling

### Common Error Responses

**Validation Error (422):**
```json
{
  "detail": [
    {
      "loc": ["body", "rules"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

**Server Error (500):**
```json
{
  "detail": "Failed to apply sorting: Database connection error"
}
```

## Usage Examples

### Frontend JavaScript/TypeScript
```typescript
// Apply sorting
const sortingResponse = await fetch('/api/v1/phase2/apply-sorting', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    rules: {
      preamble_first: true,
      numeric_order: true,
      alphabetical_fallback: true
    },
    scope: 'all'
  })
});

// Apply cleaning
const cleaningResponse = await fetch('/api/v1/phase2/apply-cleaning', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    mappings: [
      { source: 'number', target: 'section_number', enabled: true },
      { source: 'definition', target: 'section_content', enabled: true }
    ],
    scope: 'all'
  })
});
```

### cURL Examples
```bash
# Apply sorting
curl -X POST "http://localhost:8000/api/v1/phase2/apply-sorting" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "rules": {
      "preamble_first": true,
      "numeric_order": true,
      "alphabetical_fallback": true
    },
    "scope": "all"
  }'

# Apply cleaning
curl -X POST "http://localhost:8000/api/v1/phase2/apply-cleaning" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "mappings": [
      {"source": "number", "target": "section_number", "enabled": true}
    ],
    "scope": "all"
  }'
```

## Implementation Details

### Sorting Logic
The sorting implementation uses a three-tier system:
1. **Preamble (Priority 0):** Sections with `number` field containing "preamble" (case-insensitive)
2. **Numeric (Priority 1):** Sections with numeric `number` fields, sorted by value
3. **Text (Priority 2):** All other sections, sorted alphabetically

### Field Cleaning Logic
The cleaning implementation:
1. Processes each enabled mapping in order
2. Copies values from source fields to target fields
3. Removes source fields if different from target fields
4. Preserves original data by outputting to separate collection
5. Tracks all changes for reporting

### Database Operations
- **Source Collection:** `normalized_statutes` (default)
- **Target Collections:** `sorted_statutes`, `cleaned_statutes`
- **Operation:** Replaces entire target collection with processed documents
- **Preservation:** Original data remains untouched in source collection

## Testing
Both endpoints have been tested with:
- ✅ Request validation (missing fields, invalid formats)
- ✅ Authentication requirements
- ✅ Database connectivity
- ✅ OpenAPI documentation generation
- ✅ Frontend integration

---
*Documentation created on August 14, 2025*
