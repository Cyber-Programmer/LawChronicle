# Phase 5 Configuration Updates - Frontend Source Selection

## 📋 **What Phase5Config Does**

Phase5Config controls **Phase 5: Contextual Statute Grouping & Versioning** - the system that:

1. **Groups Related Statutes**: Finds statutes that belong together (original law + amendments)
2. **Uses AI Analysis**: Analyzes preamble + first 5 sections for contextual similarity (not just title matching)
3. **Creates Nested Documents**: Puts all related statutes into single documents with versioning metadata
4. **Enforces Province Boundaries**: Never groups statutes from different provinces

## 🎯 **Updated Configuration**

```python
class Phase5Config(BaseModel):
    source_database: Optional[str] = None        # Frontend selectable
    source_collection: Optional[str] = None      # Frontend selectable
    target_database: str = "Grouped-Statutes"    # Consistent naming
    target_collection: Optional[str] = None      # Auto-generated

    def get_target_collection(self) -> str:
        """Generate target collection name from source collection."""
        if self.target_collection:
            return self.target_collection          # User override
        if self.source_collection:
            return f"grouped_{self.source_collection}"  # Dynamic: batch_1 → grouped_batch_1
        return "grouped_statutes"                  # Fallback
```

### **Previous vs New Setup**

| Field | Previous | Updated | Purpose |
|-------|----------|---------|---------|
| `target_database` | `"Phase5-Groups"` | `"Grouped-Statutes"` | Matches naming pattern like "Batched-Statutes" |
| `target_collection` | `"grouped_statutes"` | `Optional[str] = None` | Derived from source collection dynamically |

### **New Dynamic Collection Naming**

```python
class Phase5Config(BaseModel):
    source_database: Optional[str] = None        # Frontend selectable
    source_collection: Optional[str] = None      # Frontend selectable  
    target_database: str = "Grouped-Statutes"    # Consistent naming
    target_collection: Optional[str] = None      # Auto-generated
    
    def get_target_collection(self) -> str:
        """Generate target collection name from source collection."""
        if self.target_collection:
            return self.target_collection          # User override
        if self.source_collection:
            return f"grouped_{self.source_collection}"  # Dynamic: batch_1 → grouped_batch_1
        return "grouped_statutes"                  # Fallback
```

### **Example Collection Mapping**

| Source Collection | Target Collection | Result |
|-------------------|-------------------|--------|
| `batch_1` | `grouped_batch_1` | Groups from batch 1 |
| `batch_2` | `grouped_batch_2` | Groups from batch 2 |
| `normalized_statutes` | `grouped_normalized_statutes` | Groups from normalized data |
| (autodetected) | `grouped_statutes` | Default fallback |

## 🖥️ **Frontend Selection Capabilities**

### **Available API Endpoints**

```bash
# Get available source collections
GET /api/v1/phase5/collections
Response: ["batch_1", "batch_2", "batch_3", ...]

# Get available provinces  
GET /api/v1/phase5/provinces
Response: ["Punjab", "Sindh", "Balochistan", ...]

# Start grouping with user selection
POST /api/v1/phase5/start-grouping
{
  "config": {
    "source_database": "Date-Enriched-Batches",
    "source_collection": "batch_1",
    "batch_size": 30
  }
}
```

### **Frontend UI Flow**

1. **Load Options**: Call `/collections` and `/provinces` to populate dropdowns
2. **User Selection**: Let user choose database, collection, and processing options
3. **Submit Request**: Send selected config to `/start-grouping`
4. **Monitor Progress**: Stream progress via `/progress-stream`
5. **View Results**: Access grouped results via `/grouped-statutes`

### **Configuration Options User Can Control**

| Setting | Frontend Control | Default | Purpose |
|---------|-----------------|---------|---------|
| Source Database | Dropdown selection | Auto-detect | Which database to read from |
| Source Collection | Dropdown selection | Auto-detect | Which collection within database |
| Batch Size | Number input | 40 | How many statutes per AI batch |
| Use Azure OpenAI | Checkbox | true | Enable AI grouping vs rule-based |
| Max Sections | Number input | 5 | How many sections for context |
| Context Length | Number input | 5000 | Max characters for AI analysis |

## 🏗️ **Benefits of New Setup**

### **✅ Parallel Processing**

- Different source collections → Different target collections
- Can run `batch_1`, `batch_2`, `batch_3` grouping simultaneously
- No conflicts or overwrites

### **✅ Clear Organization**

```python
Grouped-Statutes Database:
├── grouped_batch_1     (Groups from batch 1)
├── grouped_batch_2     (Groups from batch 2)
├── grouped_batch_3     (Groups from batch 3)
└── grouped_statutes    (Default/mixed groups)
```

### **✅ Frontend Flexibility**

- User picks exact source data to process
- Can reprocess specific batches
- Can compare grouping results across different sources
- Can process provinces separately if needed

### **✅ Backward Compatibility**

- Autodetection still works if user doesn't specify
- API contract unchanged - just enhanced
- Existing grouped data remains accessible

## 📊 **Example Usage Scenarios**

### **Scenario 1: Process Specific Province**

```json
{
  "config": {
    "source_database": "Date-Enriched-Batches",
    "source_collection": "batch_1",
    "batch_size": 20
  }
}
```

Result: `Grouped-Statutes.grouped_batch_1`

### **Scenario 2: Reprocess with Different Settings**

```json
{
  "config": {
    "source_database": "Date-Enriched-Batches", 
    "source_collection": "batch_2",
    "batch_size": 50,
    "max_sections": 3
  }
}
```

Result: `Grouped-Statutes.grouped_batch_2`

### **Scenario 3: Custom Target Override**

```json
{
  "config": {
    "source_collection": "batch_1",
    "target_collection": "punjab_groups_v2"
  }
}
```

Result: `Grouped-Statutes.punjab_groups_v2`

## 🎯 **Summary**

✅ **Frontend Selection**: Users can now select source database and collection via dropdown menus  
✅ **Dynamic Naming**: Target collections automatically named based on source selection  
✅ **Parallel Processing**: Multiple grouping operations can run simultaneously without conflicts  
✅ **Consistent Database Naming**: Uses "Grouped-Statutes" to match project patterns  
✅ **API Ready**: All endpoints support the new configuration with backward compatibility  

The updated Phase5Config provides maximum flexibility while maintaining ease of use and clear organization!
