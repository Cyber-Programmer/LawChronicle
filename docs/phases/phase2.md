# Phase 2 — Database Normalization

Scope: Normalize raw statutes into a standardized structure and collections.

Status: Implemented (backend API available)

Base URL: http://localhost:8000/api/v1/phase2

Key Inputs/Outputs
- Input: MongoDB (default mongodb://localhost:27017), source collection `raw_statutes`
- Outputs: normalized collections (default `normalized_statutes`, `sorted_statutes`), plus preview APIs
- Config Model: NormalizationConfig in backend (source/target collections, database names)

Endpoints (selected)
- POST /generate-scripts — generate helper normalization scripts (diagnostic/dev aid)
- POST /execute-normalization — run normalization end-to-end
- POST /preview-normalized-structure — preview target schema from samples
- POST /normalization-status — progress/status of normalization task
- POST /preview-normalized — preview normalized docs without writing
- POST /rollback — rollback changes if required

Notes
- The implementation includes detailed logging to trace normalization steps
- Field-name handling attempts to map raw-case fields to normalized names
- Ensure MongoDB is running and env variables in `backend/env.example` are configured
