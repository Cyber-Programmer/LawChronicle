# LawChronicle CLI Reference Files

This folder contains copies of all the original CLI scripts and utility files from the LawChronicle project, organized by pipeline phase and purpose.

**Generated on:** 2025-08-11 20:43:27
**Total files copied:** 57
**Total files skipped:** 0

## 📁 Directory Structure

### 01_data_ingestion/
- **connect_existing_db.py** - Connects to existing databases and provides data access utilities

### 02_db_normalization/
- **normalize_structure.py** - Core normalization script for processing raw statutes, normalizing names, and grouping sections
- **create_clean_db.py** - Loads normalized statutes, normalizes names, and creates clean MongoDB collections

### 03_field_cleaning_splitting/
- **bring_common_fields_up.py** - Identifies and moves common fields from sections to statute level
- **cleaning_single_section.py** - Cleans up statutes with single empty sections
- **cleanup_statutes.py** - General statute cleanup and field standardization
- **drop_unnecessary_fields.py** - Removes unnecessary or redundant fields
- **remove_preamble_duplicates_advanced.py** - Advanced duplicate removal for preamble sections
- **sort_sections.py** - Sorts sections within statutes using logical ordering
- **split_cleaned_statute.py** - Splits cleaned statutes into individual section documents

### 04_date_processing/
- **fill_missing_dates.py** - Loads date mappings from Excel and updates missing dates in MongoDB
- **fill_dates_grouped_batches.py** - Batch processing for filling missing dates
- **parse_dates.py** - Date parsing utilities and validation functions
- **search_dates.py** - Searches for and extracts dates from statute text
- **check_missing_dates.py** - Analyzes statutes to identify missing date information
- **config_ai_extractor.json** - Configuration for AI-based date extraction
- **config_search_dates.json** - Configuration for date search processes
- **README_AI_Date_Extractor.md** - Documentation for AI date extraction
- **requirements_ai_extractor.txt** - Dependencies for AI date extraction

### 05_statute_versioning/
- **assign_statute_versions.py** - Assigns version labels to statutes within base groups
- **group_statutes_by_base.py** - Groups statutes by base name using semantic similarity
- **remove_duplicates.py** - Removes duplicate statutes based on similarity thresholds
- **config_assign_versions.json** - Configuration for statute versioning
- **config_group_statutes.json** - Configuration for statute grouping
- **README_versioning.md** - Documentation for statute versioning

### 06_section_versioning/
- **assign_section_versions.py** - Groups sections by base statute and assigns versions
- **create_grouped_statute_db.py** - Creates grouped database structure for section versioning
- **split_sections.py** - Splits statutes into individual section documents
- **generate_metadata_summary.py** - Generates metadata summaries for section versioning
- **README_section_versioning.md** - Documentation for section versioning
- **requirements.txt** - Dependencies for section versioning

### 07_export_pipeline/
- **export_to_json.py** - Exports processed statutes to JSON format
- **export_to_mongo.py** - Exports processed statutes to MongoDB with proper indexing

### utils/
- **phase_logger.py** - Core logging infrastructure for pipeline phase decisions
- **metadata_helper.py** - Utilities for saving metadata files
- **gpt_cache.py** - Caching system for GPT API calls
- **gpt_rate_limiter.py** - Rate limiting utilities for GPT API calls
- **gpt_fallbacks.py** - Fallback strategies for GPT API failures
- **gpt_prompt_optimizer.py** - GPT prompt optimization utilities
- **gpt_batcher.py** - GPT request batching utilities
- **gpt_monitor.py** - GPT API usage monitoring
- **gpt_async.py** - Asynchronous GPT API call utilities
- **delete_dbs.py** - Database cleanup utilities
- **reorganize_files.py** - File organization utilities
- **config.py** - Configuration utilities
- **db_connection.py** - Database connection utilities

### config/
- **azure_openai_config.json** - Azure OpenAI configuration
- **requirements.txt** - Project dependencies

### docs/
- **data_pipeline_architecture.md** - Pipeline architecture documentation
- **CONSOLIDATION_VALIDATION_GUIDE.md** - Validation guide
- **INTELLIGENT_GROUPING_EXECUTIVE_SUMMARY.md** - Intelligent grouping summary
- **INTELLIGENT_GROUPING_TECHNICAL_IMPLEMENTATION.md** - Technical implementation details
- **LAWCHRONICLE_TECHNICAL_INTERVIEW_PREPARATION.md** - Technical interview preparation
- **PROJECT_DESCRIPTION_AMENDED.md** - Project description
- **LAWCHRONICLE_COMPREHENSIVE_PIPELINE.md** - Comprehensive pipeline documentation
- **LAWCHRONICLE_PIPELINE_FLOW.md** - Pipeline flow documentation
- **INTEGRATION_GUIDE.md** - Integration guide

## 🔄 Migration Notes

These files serve as reference material during the migration from CLI-based processing to the new web-based architecture using:
- **Frontend**: React.js
- **Backend**: FastAPI
- **Database**: MongoDB

## 📊 Copy Statistics

- **Successfully copied:** 57 files
- **Skipped:** 0 files
- **Errors:** 0 errors

