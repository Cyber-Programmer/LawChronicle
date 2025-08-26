# Phase 5: Statute Grouping & Versioning

## Overview

Phase 5 implements intelligent statute grouping and versioning functionality for the LawChronicle legal document processing pipeline. This phase takes date-enriched statutes from Phase 4 and groups them by similarity, then creates chronologically ordered versions within each group.

## Architecture

### Core Components

1. **Phase5Service** (`backend/app/core/services/phase5_service.py`)
   - Main business logic for grouping and versioning
   - Implements rule-based and AI-powered similarity detection
   - Handles chronological sorting and version assignment

2. **Phase 5 Endpoints** (`backend/app/api/v1/endpoints/phase5.py`)
   - RESTful API endpoints under `/api/v1/phase5/`
   - Server-Sent Events for real-time progress updates
   - CRUD operations for grouped statutes

3. **Pydantic Models** (`shared/types/common.py`)
   - Type-safe data models for configuration and responses
   - Validation and serialization for API communication

## Grouping Algorithm

### Rule-Based Grouping
Statutes are initially grouped by a composite key consisting of:
- **Base Name**: Statute name with version indicators removed
- **Province**: Geographic jurisdiction
- **Statute Type**: Act, Ordinance, Code, etc.
- **Legal Category**: Municipal Law, Criminal Law, etc.

### AI-Enhanced Similarity Detection
- Uses Azure OpenAI (GPT-4o) for semantic similarity analysis
- Compares statute names, preambles, and key provisions
- Configurable similarity threshold (default: 0.85)
- TODO: Implement actual Azure OpenAI integration

### Versioning Logic
Within each group:
1. Extract and validate dates from multiple date fields
2. Sort statutes chronologically (oldest first)
3. Assign version numbers starting from 1
4. Mark the oldest statute as the base version
5. Handle undated statutes as higher versions

## API Endpoints

### Core Processing
- `POST /api/v1/phase5/start-grouping` - Start the grouping process
- `GET /api/v1/phase5/status` - Get current processing status
- `GET /api/v1/phase5/progress` - Get processing progress
- `POST /api/v1/phase5/stop` - Stop current processing
- `GET /api/v1/phase5/progress-stream` - Real-time progress updates (SSE)

### Data Access
- `GET /api/v1/phase5/preview-grouping` - Preview grouping without full processing
- `GET /api/v1/phase5/grouped-statutes` - Paginated list of grouped statutes
- `GET /api/v1/phase5/groups` - Paginated list of statute groups

## Configuration

### Phase5Config Model
```python
class Phase5Config(BaseModel):
    source_database: str = "Date-Enriched-Batches"
    target_database: str = "Grouped-Statutes"
    target_collection: str = "grouped_statutes"
    similarity_threshold: float = 0.85  # AI similarity threshold
    batch_size: int = 50               # Processing batch size
    use_azure_openai: bool = True      # Enable AI similarity detection
```

### Environment Variables
```env
AZURE_OPENAI_ENDPOINT=https://your-openai.openai.azure.com/
AZURE_OPENAI_KEY=your-api-key
AZURE_OPENAI_MODEL=gpt-4o
MONGODB_URL=mongodb://localhost:27017
```

## Data Models

### GroupedStatute
Represents a single statute within a group with version information:
```python
{
    "original_statute_id": "64f1a2b3c4d5e6f7g8h9i0j1",
    "group_id": "uuid-v4-group-identifier",
    "base_name": "Criminal Procedure Code",
    "province": "Federal",
    "statute_type": "Code",
    "legal_category": "Criminal Law",
    "version_number": 1,
    "is_base_version": true,
    "date_enacted": "1898-03-25T00:00:00Z",
    "similarity_score": 1.0,
    "statute_data": { /* original statute document */ }
}
```

### StatuteGroup
Represents a group of related statutes:
```python
{
    "group_id": "uuid-v4-group-identifier",
    "base_name": "Criminal Procedure Code",
    "province": "Federal",
    "statute_type": "Code",
    "legal_category": "Criminal Law",
    "base_statute_id": "64f1a2b3c4d5e6f7g8h9i0j1",
    "statutes": [ /* array of GroupedStatute objects */ ],
    "version_count": 3
}
```

## Base Name Extraction

The service automatically extracts base names by removing common version indicators:
- Amendment patterns: `(amendment)`, `amendment 2020`
- Year patterns: `2020`, `act 2020`
- Revision patterns: `(revised)`, `revised 2`
- Number patterns: `(no. 5)`, `no. 12`

Example transformations:
- `"Companies Act 1984 (Amendment) 2020"` → `"Companies Act"`
- `"Criminal Procedure Code 1898 (No. 5)"` → `"Criminal Procedure Code 1898"`
- `"Income Tax Ordinance 2001 Revised"` → `"Income Tax Ordinance 2001"`

## Error Handling

The service implements comprehensive error handling:
- Database connection failures
- Invalid date formats
- Azure OpenAI API errors (with fallback)
- Processing interruption support
- Validation errors for malformed data

## Performance Considerations

- **Batch Processing**: Configurable batch sizes for large datasets
- **Progress Tracking**: Real-time progress updates via Server-Sent Events
- **Memory Management**: Streaming processing to handle large collections
- **Parallel Processing**: Asynchronous operations where possible

## Testing

Run the validation script to test the implementation:
```bash
cd /path/to/LawChronicle
python validate_phase5.py
```

The validation script tests:
- Service initialization and configuration
- Base name extraction logic
- Date parsing functionality
- API model validation
- Endpoint structure verification

## Integration with Other Phases

### Input (Phase 4)
- Reads from `Date-Enriched-Batches` database
- Expects collections named `batch_1`, `batch_2`, etc.
- Requires date-enriched statute documents

### Output (Phase 6+)
- Writes to `Grouped-Statutes.grouped_statutes` collection
- Provides versioned statutes for further processing
- Maintains references to original statute IDs

## Monitoring and Debugging

### Logging
The service provides detailed logging for:
- Grouping decisions and similarity scores
- Processing progress and performance metrics
- Error conditions and recovery actions
- Azure OpenAI API interactions

### Status Monitoring
- Real-time progress via `/progress-stream` endpoint
- Processing statistics via `/status` endpoint
- Database document counts and collection status

## Future Enhancements

1. **Advanced AI Integration**
   - Implement actual Azure OpenAI integration
   - Add support for multiple AI providers
   - Implement confidence scoring and uncertainty handling

2. **Similarity Algorithms**
   - Text-based similarity using TF-IDF or embeddings
   - Structural similarity based on section organization
   - Legal domain-specific similarity metrics

3. **User Interface**
   - Visual similarity comparison tools
   - Manual grouping override capabilities
   - Conflict resolution interfaces

4. **Performance Optimization**
   - Caching for similarity computations
   - Parallel processing for large datasets
   - Incremental processing for new statutes

## Troubleshooting

### Common Issues

1. **Import Errors**
   - Ensure the shared types are accessible via Python path
   - Check that all dependencies are installed

2. **Database Connection**
   - Verify MongoDB is running and accessible
   - Check connection string in environment variables

3. **Azure OpenAI Integration**
   - Verify API credentials are configured
   - Check network connectivity to Azure endpoints
   - Monitor API rate limits and quotas

4. **Memory Issues**
   - Reduce batch_size in configuration
   - Monitor memory usage during large datasets
   - Consider chunked processing for very large collections
