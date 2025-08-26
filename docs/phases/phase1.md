# Phase 1 — Data Ingestion & Analysis

Scope: Connect to MongoDB, inspect raw collection, and provide analysis endpoints to help design normalization.

Status: Implemented (backend API available)

Base URL: http://localhost:8000/api/v1/phase1

Key Inputs/Outputs
- Input DB: settings.mongodb_url (default mongodb://localhost:27017)
- Database: settings.mongodb_db
- Collection: raw_statutes
- Output: JSON responses with connection, stats, sample data, and analysis.

Endpoints
- GET /connect — quick connection check; returns database and collection info
- GET /database-info — collection stats, sample document, fields
- GET /field-stats — coverage, empties, type sample per field
- GET /sample-data?page&pagesize&field_filter — paged sample documents
- GET /statute-names — attempts to list statute name field and a distribution
- GET /health — DB health and response time
- GET /analyze — structure analysis from sample docs

Notes
- These endpoints rely on MongoDB running on localhost:27017 (or configured via environment variables)
- Sensitive configs should be provided via env; do not commit secrets
