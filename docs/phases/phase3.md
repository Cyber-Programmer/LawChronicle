# Phase 3 — Field Cleaning & Splitting

Scope: Split normalized statutes into batches and clean fields at statute/section level.

Status: Implemented (backend API available)

Base URL: http://localhost:8000/api/v1/phase3

Key Inputs/Outputs
- Input: MongoDB source DB (default `Statutes`), collection `normalized_statutes`
- Output: Batched DB (default `Batched-Statutes`) with collections `batch1`, `batch2`, ...
- Metadata: JSON files generated to `backend/app/api/metadata` folder

Primary Models
- Phase3Config: source/target DBs, target collection prefix, batch size, AI flags
- BatchCleaningConfig: batch selection and cleaning options

Endpoints
- GET /status — current status summary for phase-3 processing
- POST /start-section-splitting — create batch collections with metadata
- POST /start-field-cleaning — clean fields across batches/statutes/sections
- POST /preview-batches — show planned batches before writing
- POST /statistics — compute statistics about batches and contents
- POST /rollback — revert changes (when supported by operation)
- POST /generate-metadata — (re)generate metadata for existing batches
- GET /history — list prior metadata/history files
- GET /history/{filename} — fetch a specific metadata file
- POST /clean-batches — clean content across selected or all batches
- POST /available-batches — list batch collection names

Notes
- Default connection is `mongodb://localhost:27017`
- Pakistani province filters and content checks are built-in to help keep dataset in scope
- Large operations prefer sync `pymongo` for batch writes where applicable
