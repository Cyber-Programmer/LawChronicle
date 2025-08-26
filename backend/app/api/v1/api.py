from fastapi import APIRouter
from .endpoints import auth, database, phase1, phase2, phase3, phase4, phase4_search, phase5

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(database.router, prefix="/database", tags=["Database"])
api_router.include_router(phase1.router, prefix="/phase1", tags=["Phase 1: Data Ingestion"])
api_router.include_router(phase2.router, prefix="/phase2", tags=["Phase 2: Database Normalization"])
api_router.include_router(phase3.router, prefix="/phase3", tags=["Phase 3: Field Cleaning & Splitting"])
api_router.include_router(phase4.router, prefix="/phase4", tags=["Phase 4: Enhanced Date Processing"])
api_router.include_router(phase4_search.router, prefix="/phase4/search", tags=["Phase 4: Date Search"])
api_router.include_router(phase5.router, prefix="/phase5", tags=["Phase 5: Statute Grouping & Versioning"])
