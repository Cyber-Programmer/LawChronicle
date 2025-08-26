# LawChronicle AI Coding Agent Instructions

## Architecture Overview

**LawChronicle** is a 6-phase legal document processing pipeline with a React/FastAPI stack. The system transforms raw Pakistani legal statutes through progressive data refinement phases, each with dedicated database collections and API endpoints.

### Key Architecture Patterns

- **Phase-based Processing**: Each phase (`/api/v1/phase1-4`) operates on specific database collections with consistent input→process→output flows
- **Database Per Phase**: `raw_statutes` → `normalized_statutes` → `batch_*` → `Date-Enriched-Batches`, etc.
- **Service-Endpoint-Component Triad**: Backend services (`core/services/`) ↔ API endpoints (`api/v1/endpoints/`) ↔ React page components (`pages/Phase*.tsx`)

## Critical Development Workflows

### Startup Sequence
```bash
# Use project batch files - they handle correct directory context
start_lawchronicle.bat    # Starts both backend:8000 and frontend:3000
stop_lawchronicle.bat     # Kills both processes
restart_lawchronicle.bat  # Clean restart
```

### Backend Development
```bash
cd backend
python -m uvicorn main:app --reload  # Auto-reload on changes
```
- **FastAPI docs**: `http://localhost:8000/docs`
- **Phase endpoints**: `/api/v1/phase{1-4}/status|start-*|preview-*`
- **MongoDB**: Default `mongodb://localhost:27017` with multiple databases per phase

### Frontend Development 
```bash
cd frontend
npm start  # React dev server with proxy to backend
```
- **Component structure**: Each phase has dedicated page (`Phase*.tsx`) + supporting components in `/components/phase*/`
- **State pattern**: Phase progress tracked in `utils/phaseProgress.ts`

## Phase-Specific Patterns

### Data Processing Flow
1. **Phase 1**: Raw data ingestion (`raw_statutes` collection)
2. **Phase 2**: Normalization (`normalized_statutes` with `Statute_Name` + `Sections[]`)
3. **Phase 3**: Batch splitting (`batch_1`, `batch_2`, etc. in `Batched-Statutes` DB)
4. **Phase 4**: AI date enrichment (Azure OpenAI integration)

### Configuration Models
Each phase uses Pydantic models for configuration:
```python
class Phase3Config(BaseModel):
    source_database: str = "Statutes"
    target_database: str = "Batched-Statutes" 
    batch_size: int = 10
```

### API Response Patterns
```python
# Standard response wrapper
return BaseResponse(success=True, message="...", data=result)

# Progress tracking via SSE
async for progress in service.process_*():
    yield {"status": "processing", "progress": 75}
```

## Integration Points

### AI Services (Phase 4+)
- **Azure OpenAI**: Configure via environment variables (`AZURE_OPENAI_*`)
- **Service pattern**: `Phase4Service._call_azure_openai()` with rate limiting
- **Fallback handling**: Always provide non-AI backup workflows

### Database Patterns
- **Motor async MongoDB**: `AsyncIOMotorClient` in all services
- **Collection naming**: Phase-specific prefixes (`batch_`, `normalized_`, etc.)
- **Cross-phase data flow**: Each phase reads from previous phase's output collection

### Authentication
- **JWT tokens**: Optional auth with `optional_current_user` dependency
- **Role-based**: Admin/reviewer/user permissions via `core/auth.py`

## Project-Specific Conventions

### File Organization
- **Services**: Business logic in `backend/app/core/services/`
- **Shared types**: `shared/types/common.py` for cross-platform Pydantic models
- **Metadata tracking**: JSON files in `backend/app/api/metadata/`

### Error Handling
```python
# Consistent error pattern across all endpoints
try:
    result = await service.process()
    return {"success": True, "data": result}
except Exception as e:
    logger.error(f"Operation failed: {str(e)}")
    raise HTTPException(status_code=500, detail=str(e))
```

### Frontend State Management
- **Phase progress**: Centralized in `utils/phaseProgress.ts`
- **API calls**: Direct fetch() calls, no external state library
- **Real-time updates**: Server-Sent Events for background processing

## Development Guidelines

- **Phase isolation**: New phases should follow the Service→Endpoint→Component pattern
- **Database evolution**: Each phase creates new collections, preserves input data
- **AI integration**: Always provide TODO placeholders for external LLM calls, never hardcode API keys
- **Background processing**: Use FastAPI BackgroundTasks with SSE progress updates
- **MongoDB naming**: Follow `{operation}-{collection}-{phase}` naming convention

## Key Files for Context
- `backend/main.py`: FastAPI app entry point
- `backend/app/api/v1/api.py`: Router configuration  
- `frontend/src/pages/Dashboard.tsx`: Phase orchestration
- `shared/types/common.py`: Cross-platform type definitions
- `backend/app/core/config.py`: Environment configuration
