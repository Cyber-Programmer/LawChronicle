"""
Date Search Service for Phase 4

Handles searching for missing dates in processed documents using AI assistance,
providing review capabilities, and managing the insertion workflow.
"""

import asyncio
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, Any, List, Optional, AsyncGenerator
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
import pandas as pd
from io import BytesIO
import re
from dateutil import parser
import openai
from openai import AsyncAzureOpenAI


class Phase4SearchService:
    def __init__(self):
        self.client = AsyncIOMotorClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"))
        self.source_db: AsyncIOMotorDatabase = self.client.get_database("Date-Enriched-Batches")
        self.target_db: AsyncIOMotorDatabase = self.client.get_database("Date-Enriched-Batches")
        self.search_db: AsyncIOMotorDatabase = self.client.get_database("Date-Search-Results")
        
        # Initialize Azure OpenAI client
        self.azure_client = None
        self.config = None
        self._load_config()
        self._init_azure_client()
        
        self._should_stop = False
        
    def _load_config(self):
        """Load configuration from config file"""
        try:
            config_path = os.path.join(os.path.dirname(__file__), "../../config/azure_openai_config.json")
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    self.config = json.load(f)
                print(f"[INFO] Loaded configuration from {config_path}")
            else:
                print(f"[WARNING] Config file not found at {config_path}")
        except Exception as e:
            print(f"[ERROR] Failed to load config: {e}")
            self.config = None
        
    def _init_azure_client(self):
        """Initialize Azure OpenAI client using config file or environment variables"""
        try:
            # Try config file first
            if self.config and "azure_openai" in self.config:
                azure_config = self.config["azure_openai"]
                api_key = azure_config.get("api_key")
                endpoint = azure_config.get("endpoint")
                api_version = azure_config.get("api_version", "2024-02-15-preview")
                
                if api_key and endpoint:
                    self.azure_client = AsyncAzureOpenAI(
                        api_key=api_key,
                        api_version=api_version,
                        azure_endpoint=endpoint
                    )
                    print("[INFO] Azure OpenAI client initialized from config file")
                    return
            
            # Fallback to environment variables
            api_key = os.getenv("AZURE_OPENAI_API_KEY")
            endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
            if api_key and endpoint:
                self.azure_client = AsyncAzureOpenAI(
                    api_key=api_key,
                    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
                    azure_endpoint=endpoint
                )
                print("[INFO] Azure OpenAI client initialized from environment variables")
            else:
                print("[WARNING] Azure OpenAI credentials not found in config or environment")
                
        except Exception as e:
            print(f"[WARNING] Azure OpenAI client initialization failed: {e}")
            self.azure_client = None
    
    async def get_available_collections(self) -> List[str]:
        """Get list of available date-enriched collections"""
        try:
            collections = await self.source_db.list_collection_names()
            # Filter collections that look like batch collections
            batch_collections = [c for c in collections if re.match(r"^batch_\d+$", c)]
            batch_collections.sort(key=lambda x: int(x.split("_")[-1]))
            return batch_collections
        except Exception as e:
            print(f"[ERROR] Failed to get collections: {e}")
            return []
    
    async def scan_missing_dates(
        self, 
        collection_names: List[str] = None,
        progress_callback: callable = None
    ) -> Dict[str, Any]:
        """
        Scan for documents with missing dates in specified collections
        
        Returns summary with missing dates statistics and sample documents
        """
        try:
            if not collection_names:
                collection_names = await self.get_available_collections()
            
            results = {
                "scan_timestamp": datetime.utcnow().isoformat(),
                "collections_scanned": collection_names,
                "summary": {
                    "total_documents": 0,
                    "documents_with_dates": 0,
                    "documents_missing_dates": 0,
                    "missing_percentage": 0.0
                },
                "collection_breakdown": {},
                "sample_missing": []
            }
            
            total_docs = 0
            total_missing = 0
            sample_missing = []
            
            for collection_name in collection_names:
                if self._should_stop:
                    break
                    
                collection = self.source_db[collection_name]
                
                # Count total documents
                collection_total = await collection.count_documents({})
                
                # Count documents with missing dates.
                # A document should be considered missing only when BOTH canonical date fields
                # ('Date' and 'Date_Enacted') are absent/empty. Previously an $or across both
                # fields caused documents to be counted as missing when either field was missing,
                # which inflated missing counts. Use $and of per-field $or conditions.
                missing_query = {
                    "$and": [
                        {"$or": [
                            {"Date": {"$in": ["", None]}},
                            {"Date": {"$exists": False}}
                        ]},
                        {"$or": [
                            {"Date_Enacted": {"$in": ["", None]}},
                            {"Date_Enacted": {"$exists": False}}
                        ]}
                    ]
                }
                collection_missing = await collection.count_documents(missing_query)
                
                # Get sample missing documents
                missing_docs = []
                if collection_missing > 0:
                    cursor = collection.find(missing_query).limit(5)
                    async for doc in cursor:
                        missing_docs.append({
                            "_id": str(doc["_id"]),
                            "Statute_Name": doc.get("Statute_Name", "Unknown"),
                            "Province": doc.get("Province", "Unknown"),
                            "collection": collection_name
                        })
                        
                sample_missing.extend(missing_docs)
                
                results["collection_breakdown"][collection_name] = {
                    "total_documents": collection_total,
                    "missing_dates": collection_missing,
                    "missing_percentage": (collection_missing / collection_total * 100) if collection_total > 0 else 0
                }
                
                total_docs += collection_total
                total_missing += collection_missing
                
                if progress_callback:
                    progress = len(results["collection_breakdown"]) / len(collection_names) * 100
                    await progress_callback({
                        "progress": progress,
                        "current_collection": collection_name,
                        "collections_processed": len(results["collection_breakdown"]),
                        "total_collections": len(collection_names)
                    })
            
            # Update summary
            results["summary"].update({
                "total_documents": total_docs,
                "documents_missing_dates": total_missing,
                "documents_with_dates": total_docs - total_missing,
                "missing_percentage": (total_missing / total_docs * 100) if total_docs > 0 else 0
            })
            
            results["sample_missing"] = sample_missing[:20]  # Limit samples
            
            return results
            
        except Exception as e:
            print(f"[ERROR] Scan missing dates failed: {e}")
            raise e
    
    async def export_missing_dates_to_excel(self, collection_names: List[str] = None) -> bytes:
        """
        Export documents with missing dates to Excel format for review
        """
        try:
            if not collection_names:
                collection_names = await self.get_available_collections()
            
            all_missing_docs = []
            
            for collection_name in collection_names:
                collection = self.source_db[collection_name]
                
                missing_query = {
                    "$or": [
                        {"Date": {"$in": ["", None]}},
                        {"Date": {"$exists": False}}
                    ]
                }
                
                cursor = collection.find(missing_query)
                async for doc in cursor:
                    # Extract relevant sections for AI analysis
                    sections_text = ""
                    if "Sections" in doc and isinstance(doc["Sections"], list):
                        sections_text = " ".join([
                            section.get("Statute", section.get("Section_Text", ""))  # Try Statute field first, then Section_Text
                            for section in doc["Sections"][:3]  # First 3 sections
                        ])[:2000]  # Limit text length
                    
                    all_missing_docs.append({
                        "Collection": collection_name,
                        "Document_ID": str(doc["_id"]),
                        "Statute_Name": doc.get("Statute_Name", ""),
                        "Province": doc.get("Province", ""),
                        "Current_Date": doc.get("Date", ""),
                        "Sections_Sample": sections_text,
                        "AI_Extracted_Date": "",  # To be filled by AI
                        "Confidence_Score": "",
                        "Review_Status": "Pending",
                        "Reviewer_Comments": "",
                        "Approved_Date": "",
                        "Search_Method": ""
                    })
            
            # Create Excel file
            df = pd.DataFrame(all_missing_docs)
            
            # Create Excel with multiple sheets
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # Main data sheet
                df.to_excel(writer, sheet_name="Missing_Dates", index=False)
                
                # Summary sheet
                summary_data = {
                    "Metric": ["Total Documents", "Collections Scanned", "Export Date"],
                    "Value": [len(all_missing_docs), len(collection_names), datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")]
                }
                pd.DataFrame(summary_data).to_excel(writer, sheet_name="Summary", index=False)
                
                # Instructions sheet
                instructions = pd.DataFrame({
                    "Step": [
                        "1. Review Documents",
                        "2. AI Processing", 
                        "3. Manual Review",
                        "4. Approval",
                        "5. Upload"
                    ],
                    "Description": [
                        "Review the missing dates in the Missing_Dates sheet",
                        "Use AI Search to automatically extract dates",
                        "Review AI_Extracted_Date and Confidence_Score columns",
                        "Set Review_Status to 'Approved' for valid dates",
                        "Upload the file back to continue processing"
                    ]
                })
                instructions.to_excel(writer, sheet_name="Instructions", index=False)
            
            output.seek(0)
            return output.getvalue()
            
        except Exception as e:
            print(f"[ERROR] Export to Excel failed: {e}")
            raise e
    
    async def search_dates_with_ai(
        self,
        documents: List[Dict[str, Any]],
        progress_callback: callable = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Search for dates in documents using AI assistance
        """
        total_docs = len(documents)
        print(f"[DEBUG] search_dates_with_ai called: total_docs={total_docs}, azure_client_set={self.azure_client is not None}")

        # If Azure OpenAI is not configured, fall back to a lightweight regex-based
        # extraction so the pipeline still makes progress instead of immediately
        # returning a completed/zero-processed result.
        if not self.azure_client:
            print("[WARNING] Azure OpenAI client not configured - using regex fallback for date extraction")
            processed = 0
            for doc in documents:
                if self._should_stop:
                    break

                # Simple heuristic: look for date-like substrings using regex and parse them
                sections = doc.get("Sections_Sample", "") or ""
                # common month names regex + numeric dates
                date_match = None
                # try several loose regex patterns
                patterns = [
                    r"\b\d{1,2}[\-/ ](?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[A-Za-z]*[\-/ ,]*\d{2,4}\b",
                    r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)[\s,]*\d{1,2}[,\s]*\d{4}\b",
                    r"\b\d{1,2}[\-/]\d{1,2}[\-/]\d{2,4}\b",
                    r"\b\d{4}-\d{2}-\d{2}\b"
                ]
                for p in patterns:
                    m = re.search(p, sections, flags=re.IGNORECASE)
                    if m:
                        date_match = m.group(0)
                        break

                extracted = ""
                confidence = 30
                method = "regex_fallback"
                reasoning = ""
                if date_match:
                    try:
                        extracted = self._normalize_date(date_match)
                        confidence = 60
                        reasoning = f"Matched pattern '{date_match}'"
                    except Exception:
                        extracted = date_match
                        reasoning = "Parsed with fallback regex"

                processed += 1
                # yield a processing item for each doc to match AI flow
                yield {
                    "status": "processing",
                    "document_id": doc.get("Document_ID"),
                    "statute_name": doc.get("Statute_Name"),
                    "extracted_date": extracted,
                    "confidence": confidence,
                    "method": method,
                    "reasoning": reasoning,
                    "progress": (processed / total_docs * 100) if total_docs > 0 else 100
                }

                if progress_callback:
                    await progress_callback({
                        "processed": processed,
                        "total": total_docs,
                        "current_statute": doc.get("Statute_Name", "Unknown")
                    })

            yield {
                "status": "completed",
                "total_processed": processed,
                "progress": 100
            }
            return
        total_docs = len(documents)
        processed = 0

        for doc in documents:
            if self._should_stop:
                break

            try:
                # Extract date using AI
                extracted_info = await self._extract_date_with_ai(doc)

                yield {
                    "status": "processing",
                    "document_id": doc.get("Document_ID"),
                    "statute_name": doc.get("Statute_Name"),
                    "extracted_date": extracted_info.get("date"),
                    "confidence": extracted_info.get("confidence", 0),
                    "method": extracted_info.get("method", "ai"),
                    "reasoning": extracted_info.get("reasoning", ""),
                    "progress": (processed + 1) / total_docs * 100
                }

                processed += 1

                if progress_callback:
                    await progress_callback({
                        "processed": processed,
                        "total": total_docs,
                        "current_statute": doc.get("Statute_Name", "Unknown")
                    })

            except Exception as e:
                yield {
                    "status": "error",
                    "document_id": doc.get("Document_ID"),
                    "error": str(e),
                    "progress": (processed + 1) / total_docs * 100
                }
                processed += 1

        yield {
            "status": "completed",
            "total_processed": processed,
            "progress": 100
        }
    
    async def _extract_date_with_ai(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract date from document using AI
        """
        try:
            statute_name = document.get("Statute_Name", "")
            sections_text = document.get("Sections_Sample", "")
            
            prompt = f"""You are an expert legal document analyst. Your task is to extract the PROMULGATION/PUBLISHING DATE from the following Pakistani statute text.

IMPORTANT: Focus specifically on the date when the statute was promulgated/published in the official gazette, NOT enactment dates or other dates.

Statute: {statute_name}

Context:
{sections_text[:1500]}

Instructions:
1. Look for dates that indicate when the statute was promulgated, published, or came into force
2. Focus on official publication dates in gazettes, especially dates mentioned in:
   - Gazette notifications from any Pakistani province, federal level, or historical territories:
     * "Gazette of Pakistan" / "Pakistan Gazette"
     * "Gazette of Punjab" / "Punjab Gazette" / "Gazette of Punjab Extraordinary"
     * "Gazette of Sindh" / "Sindh Gazette" / "Gazette of Sindh Extraordinary"
     * "Gazette of Khyber Pakhtunkhwa" / "KP Gazette" / "Gazette of KPK Extraordinary"
     * "Gazette of Balochistan" / "Balochistan Gazette" / "Gazette of Balochistan Extraordinary"
     * "Gazette of Gilgit-Baltistan" / "GB Gazette"
     * "Gazette of Azad Jammu and Kashmir" / "AJK Gazette"
     * "Gazette of East Pakistan" / "East Pakistan Gazette"
     * "Gazette of West Pakistan" / "West Pakistan Gazette"
   - Official notification numbers with dates (e.g., "dated 4-3-2016", "No. PAP/Legis-2(99)/2015/1389")
   - Governor assent dates (e.g., "assented to by the Governor on March 3, 2016")
   - President assent dates (e.g., "assented to by the President on...")
   - Provincial Assembly passage dates (e.g., "passed by the Provincial Assembly on...")
3. Ignore dates that are not related to promulgation/publishing
4. If multiple dates are found, identify the most relevant one as the primary date
5. Convert all dates to DD-MMM-YYYY format (e.g., "4th March, 2016" becomes "04-Mar-2016")

Respond in JSON format:
{{
    "date": "DD-MMM-YYYY format or empty string",
    "confidence": 0-100,
    "reasoning": "Brief explanation of why this date was selected",
    "method": "gazette|notification|governor_assent|president_assent|assembly_passage|other"
}}
"""
            
            # Get configuration settings
            deployment_name = "gpt-4"
            temperature = 0.1
            max_tokens = 200
            
            if self.config and "azure_openai" in self.config:
                azure_config = self.config["azure_openai"]
                deployment_name = azure_config.get("deployment_name", deployment_name)
                model_name = azure_config.get("model", deployment_name)
            else:
                model_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", deployment_name)
            
            if self.config and "processing" in self.config:
                processing_config = self.config["processing"]
                temperature = processing_config.get("temperature", temperature)
            
            response = await self.azure_client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are an expert at extracting dates from Pakistani legal documents."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # Remove markdown code blocks if present
            if response_text.startswith("```json"):
                response_text = response_text[7:]  # Remove ```json
            elif response_text.startswith("```"):
                response_text = response_text[3:]   # Remove ```
            
            if response_text.endswith("```"):
                response_text = response_text[:-3]  # Remove closing ```
            
            response_text = response_text.strip()
            
            # Parse JSON response
            try:
                result = json.loads(response_text)
                # Validate and normalize date format
                if result.get("date"):
                    normalized_date = self._normalize_date(result["date"])
                    result["date"] = normalized_date
                return result
            except json.JSONDecodeError:
                # Fallback parsing if JSON is malformed
                return {
                    "date": "",
                    "confidence": 0,
                    "reasoning": "Failed to parse AI response",
                    "method": "ai_error"
                }
                
        except Exception as e:
            print(f"[ERROR] AI date extraction failed: {e}")
            return {
                "date": "",
                "confidence": 0,
                "reasoning": f"AI extraction error: {str(e)}",
                "method": "ai_error"
            }
    
    def _normalize_date(self, date_str: str) -> str:
        """Normalize date to DD-MMM-YYYY format"""
        if not date_str or not date_str.strip():
            return ""
        
        try:
            # Try parsing the date
            parsed_date = parser.parse(date_str, fuzzy=True)
            return parsed_date.strftime("%d-%b-%Y")
        except Exception:
            return date_str  # Return as-is if parsing fails
    
    async def save_search_results(self, results: List[Dict[str, Any]]) -> str:
        """
        Save search results to database for review
        """
        try:
            collection = self.search_db["search_sessions"]
            
            # Determine session label: if single source collection, use batch_N_timestamp shorthand
            source_cols = list(set(r.get("collection", "") for r in results))
            session_label = None
            pkt = ZoneInfo('Asia/Karachi')
            if len(source_cols) == 1 and re.match(r"^batch_\d+$", source_cols[0]):
                session_label = f"{source_cols[0]}_{datetime.now(pkt).strftime('%Y%m%d_%H%M')}"
            else:
                cols_part = "-".join(source_cols) if source_cols else "all"
                session_label = f"{cols_part}_{datetime.now(pkt).strftime('%Y%m%d_%H%M')}"

            session_doc = {
                "session_id": datetime.utcnow().strftime("%Y%m%d_%H%M%S"),
                "session_label": session_label,
                "created_at": datetime.utcnow(),
                "created_at_local": datetime.now(ZoneInfo('Asia/Karachi')).isoformat(),
                "status": "pending_review",
                "total_documents": len(results),
                "results": results,
                "metadata": {
                    "source_collections": source_cols,
                    "ai_processed": sum(1 for r in results if r.get("extracted_date")),
                    "high_confidence": sum(1 for r in results if r.get("confidence", 0) >= 80)
                }
            }
            # Debug: log session doc summary before inserting
            try:
                print(f"[DEBUG] Preparing to insert session_doc with total_documents={session_doc['total_documents']} and metadata={session_doc['metadata']}")
            except Exception:
                print("[DEBUG] Preparing to insert session_doc (failed to stringify metadata)")

            await collection.insert_one(session_doc)
            print(f"[DEBUG] Inserted session_doc with session_id={session_doc['session_id']}")
            return session_doc["session_id"]
            
        except Exception as e:
            print(f"[ERROR] Save search results failed: {e}")
            raise e
    
    async def get_search_sessions(self) -> List[Dict[str, Any]]:
        """Get list of search sessions for review"""
        try:
            collection = self.search_db["search_sessions"]
            sessions = []
            
            cursor = collection.find({}).sort("created_at", -1).limit(20)
            async for session in cursor:
                # Provide both UTC and local (Asia/Karachi) representations for display
                # Use stored fields where possible
                created_at_utc = None
                try:
                    created_at_utc = session["created_at"].astimezone().isoformat()
                except Exception:
                    created_at_utc = session.get("created_at").isoformat() if session.get("created_at") else None

                created_local = session.get("created_at_local")

                sessions.append({
                    "session_id": session["session_id"],
                    "session_label": session.get("session_label"),
                    "created_at_utc": created_at_utc,
                    "created_at_local": created_local,
                    "status": session.get("status", "pending_review"),
                    "total_documents": session.get("total_documents", 0),
                    "metadata": session.get("metadata", {})
                })
            
            return sessions
        except Exception as e:
            print(f"[ERROR] Get search sessions failed: {e}")
            return []
    
    async def stop_processing(self):
        """Stop current processing"""
        self._should_stop = True
    
    async def get_search_results(self, session_id: str) -> List[Dict[str, Any]]:
        """Get detailed results for a specific search session"""
        try:
            collection = self.search_db["search_sessions"]
            session = await collection.find_one({"session_id": session_id})
            
            if not session:
                raise ValueError(f"Search session {session_id} not found")
            
            return session.get("results", [])
        except Exception as e:
            print(f"[ERROR] Get search results failed: {e}")
            raise e
    
    async def get_session_info(self, session_id: str) -> Dict[str, Any]:
        """Get session information including metadata"""
        try:
            collection = self.search_db["search_sessions"]
            session = await collection.find_one({"session_id": session_id})
            
            if not session:
                raise ValueError(f"Search session {session_id} not found")
            # Provide UTC and local formatted timestamps for consumers
            created_at_utc = None
            try:
                created_at_utc = session["created_at"].astimezone().isoformat()
            except Exception:
                created_at_utc = session.get("created_at").isoformat() if session.get("created_at") else None

            created_local = session.get("created_at_local")

            return {
                "session_id": session["session_id"],
                "session_label": session.get("session_label"),
                "created_at_utc": created_at_utc,
                "created_at_local": created_local,
                "status": session.get("status", "pending_review"),
                "total_documents": session.get("total_documents", 0),
                "metadata": session.get("metadata", {})
            }
        except Exception as e:
            print(f"[ERROR] Get session info failed: {e}")
            raise e
    
    async def clear_search_sessions(self) -> int:
        """Clear all search session history"""
        try:
            collection = self.search_db["search_sessions"]
            result = await collection.delete_many({})
            return result.deleted_count
        except Exception as e:
            print(f"[ERROR] Clear search sessions failed: {e}")
            raise e
    
    async def delete_search_session(self, session_id: str) -> bool:
        """Delete a specific search session"""
        try:
            collection = self.search_db["search_sessions"]
            result = await collection.delete_one({"session_id": session_id})
            return result.deleted_count > 0
        except Exception as e:
            print(f"[ERROR] Delete search session failed: {e}")
            raise e
