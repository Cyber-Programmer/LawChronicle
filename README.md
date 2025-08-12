# 🚀 LawChronicle Web Application

**Modern web application for legal document processing pipeline**

## 📋 Project Overview
Convert LawChronicle from a CLI-based 7-phase legal document processing pipeline to a modern web application with React.js frontend and FastAPI backend.

## 🏗️ Architecture
- **Frontend**: React.js with TailwindCSS
- **Backend**: FastAPI with MongoDB integration
- **Database**: MongoDB (localhost:27017)
- **AI**: Azure OpenAI GPT-4o integration

## 🚀 Quick Start

### Windows Users
1. Double-click `scripts/start_all.bat` to start both frontend and backend
2. Or use individual batch files:
   - `scripts/start_backend.bat` - Backend only
   - `scripts/start_frontend.bat` - Frontend only

### Linux/Mac Users
1. Run `./scripts/start_all.sh` to start both frontend and backend
2. Or use individual scripts:
   - `./scripts/start_backend.sh` - Backend only
   - `./scripts/start_frontend.sh` - Frontend only

## 🌐 Access Points
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Database**: MongoDB Compass (localhost:27017)

## 📁 Project Structure
```
lawchronicle-web/
├── frontend/                 # React.js application
├── backend/                  # FastAPI application
├── shared/                   # Shared types and utilities
└── scripts/                  # Startup scripts
```

## 🔧 Development Setup

### Prerequisites
- Node.js 18+
- Python 3.9+
- MongoDB Compass (localhost:27017)
- Azure OpenAI API key (for AI features)

### Manual Setup
1. **Backend**:
   ```bash
   cd backend
   pip install -r requirements.txt
   python main.py
   ```

2. **Frontend**:
   ```bash
   cd frontend
   npm install
   npm start
   ```

## 📊 Pipeline Phases
1. **Data Ingestion** - Database connection and analysis
2. **Normalization** - Schema standardization
3. **Cleaning** - Field cleaning and organization
4. **Date Processing** - AI-powered date extraction
5. **Statute Versioning** - Grouping and versioning
6. **Section Versioning** - Final schema creation

## 🎯 Current Status
**Phase 0 Complete** ✅ - Foundation setup with React.js frontend, FastAPI backend, and MongoDB integration.

Ready for Phase 1: Data Ingestion Dashboard implementation.
