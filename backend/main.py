import sys
import os
from pathlib import Path

# Add parent directory to Python path for shared modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
from app.core.config import settings
from app.api.v1.api import api_router
from app.core.database import init_db

app = FastAPI(
    title="LawChronicle API",
    description="Modern web application for legal document processing pipeline",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix="/api/v1")

@app.on_event("startup")
async def startup_event():
    """Initialize database connection on startup"""
    try:
        await init_db()
        print("✅ Database connection initialized successfully")
    except Exception as e:
        print(f"⚠️  Warning: Database connection failed: {e}")
        print("   The API will start but database features may not work")
        print("   Make sure MongoDB is running on localhost:27017")

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "LawChronicle API is running!",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "active"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "LawChronicle API"}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
