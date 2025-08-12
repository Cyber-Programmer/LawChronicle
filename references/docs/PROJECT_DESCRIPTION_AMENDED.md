# 🏛️ LawChronicle – Intelligent Statute Processing for Legal AI Systems

## 👤 Name: Bahauddin Hassan
## 📘 Project: LawChronicle – Intelligent Statute Processing for Legal AI Systems

I'm working on LawChronicle, a system that processes and transforms raw Pakistani statutes into a structured, versioned legal knowledge base, ready for use in LawGPT or similar models.

## 🔹 Core Pipeline Phases:

### 1. Ingestion & Normalization
- Handles ~107,000 raw legal sections
- Normalizes schemas from mixed sources and formats
- **Tools:** Python, Pandas, Regex, json, pymongo
- **Storage:** MongoDB collections at each checkpoint

### 2. Cleaning & Filtering
- Cleans field data and splits overlong sections
- Filters for Pakistan-only content (Post-1947)
- **Storage:** Intermediate results stored in MongoDB

### 3. Enrichment & Grouping
- Date extraction using dateutil, regex
- GPT-4 + RapidFuzz used to group semantically equivalent statutes
- Achieves ~64% deduplication
- **Storage:** Grouped data persisted in MongoDB

### 4. Versioning & Export
- Section-level versioning (~68,000 versioned)
- **Final Output:** Production-ready MongoDB databases
- Batch-based: 10 batches, each ~6,800 statutes
- **Storage:** Complete pipeline results stored in MongoDB collections
- Export pipeline (JSON and MongoDB) - in development

## 🔹 Stack Overview:

**Language:** Python 3.9+
**AI/NLP:** Azure OpenAI (GPT-4), RapidFuzz
**Storage:** MongoDB (raw + processed + final output)
**UI:** Tkinter GUI for statute exploration and date processing
**Validation:** JSON Schema, business rules
**Other Libs:** NumPy, Regex, DateUtil, tqdm, openpyxl, streamlit, fastapi, uvicorn

## 🔹 Key Features:

- **Database-Centric Architecture:** All pipeline stages store results in MongoDB collections
- **Checkpoint Storage:** Intermediate results saved after each processing phase
- **Fuzzy search and real-time UI updates**
- **Multi-stage QA for data integrity**
- **Scalable architecture (handles 10x scale)**

## 🔹 Data Flow:
```
Raw Data → Normalized DB → Cleaned DB → Date-Enriched DB → Grouped DB → Versioned DB → Final Output DB
```

Each arrow represents a MongoDB collection checkpoint ensuring data persistence and recovery capabilities. 