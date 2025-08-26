import os
import json
import asyncio
import aiohttp
from openai import AsyncAzureOpenAI
from typing import AsyncGenerator, Dict, Any, List, Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from datetime import datetime
import re
import pandas as pd
import io
from bson import ObjectId

class Phase4ServiceNew:
    def __init__(self):
        # MongoDB connection
        self.mongo_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
        self.client = AsyncIOMotorClient(self.mongo_url)
        
        # Source database (Phase 3 output) - Updated to use correct database
        self.source_db = self.client["Batched-Statutes"]
        
        # Target database (Phase 4 output) 
        self.target_db = self.client["Date-Enriched-Batches"]
        
        # Azure OpenAI configuration
        self._setup_azure_openai()
        
        # Processing control
        self._should_stop = False

    def _setup_azure_openai(self):
        """Setup Azure OpenAI client with configuration."""
        try:
            # Load Azure OpenAI configuration from environment or config file
            config_path = os.path.join(os.path.dirname(__file__), "../../config/azure_openai_config.json")
            
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
                azure_config = config.get("azure_openai", {})
            else:
                azure_config = {}
            
            # Azure OpenAI settings (prioritize environment variables)
            self.azure_openai_config = {
                "api_key": os.getenv("AZURE_OPENAI_API_KEY", azure_config.get("api_key", "")),
                "endpoint": os.getenv("AZURE_OPENAI_ENDPOINT", azure_config.get("endpoint", "")),
                "deployment_name": os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", azure_config.get("deployment_name", "gpt-4o")),
                "api_version": os.getenv("AZURE_OPENAI_API_VERSION", azure_config.get("api_version", "2024-11-01-preview")),
                "model": azure_config.get("model", "gpt-4o")
            }
            
            # Processing settings
            self.processing_config = azure_config.get("processing", {
                "batch_size": 50,
                "max_retries": 3,
                "retry_delay": 1,
                "rate_limit_delay": 0.5,
                "content_limit": 4000,
                "temperature": 0.1
            })
            
            # Initialize Azure OpenAI client if API key is available
            if self.azure_openai_config["api_key"] and self.azure_openai_config["endpoint"]:
                self.azure_client = AsyncAzureOpenAI(
                    api_key=self.azure_openai_config["api_key"],
                    azure_endpoint=self.azure_openai_config["endpoint"],
                    api_version=self.azure_openai_config["api_version"]
                )
                self.ai_enabled = True
                print(f"[INFO] Azure OpenAI initialized with deployment: {self.azure_openai_config['deployment_name']}")
            else:
                self.azure_client = None
                self.ai_enabled = False
                print(f"[WARNING] Azure OpenAI not configured. AI date extraction will be disabled.")
                
        except Exception as e:
            print(f"[ERROR] Failed to setup Azure OpenAI: {str(e)}")
            self.azure_client = None
            self.ai_enabled = False

    async def get_status(self) -> Dict[str, Any]:
        """Get current processing status and statistics."""
        try:
            # Count source collections
            source_collections = await self.source_db.list_collection_names()
            batch_collections = [name for name in source_collections if name.startswith('batch_')]
            
            # Count target collections  
            target_collections = await self.target_db.list_collection_names()
            
            # Count total documents in source
            total_docs = 0
            for collection_name in batch_collections:
                collection = self.source_db[collection_name]
                count = await collection.count_documents({})
                total_docs += count
            
            # Count processed documents in target
            processed_docs = 0
            for collection_name in target_collections:
                collection = self.target_db[collection_name]
                count = await collection.count_documents({})
                processed_docs += count
            
            return {
                "total_documents": total_docs,
                "processed_documents": processed_docs,
                "source_collections": len(batch_collections),
                "target_collections": len(target_collections),
                "completion_percentage": (processed_docs / total_docs * 100) if total_docs > 0 else 0
            }
            
        except Exception as e:
            print(f"[ERROR] Failed to get status: {str(e)}")
            return {"error": str(e)}

    async def get_available_batches(self) -> List[str]:
        """Get list of available batch collections from source database."""
        try:
            collections = await self.source_db.list_collection_names()
            # Batched-Statutes uses 'batch_N' format
            batch_collections = [name for name in collections if name.startswith('batch_')]
            batch_collections.sort(key=lambda x: int(x.split('_')[1]) if '_' in x and x.split('_')[1].isdigit() else 0)
            return batch_collections
        except Exception as e:
            print(f"[ERROR] Failed to get available batches: {str(e)}")
            return []

    async def process_date_enrichment(
        self,
        processing_mode: str,
        selected_batch: Optional[str],
        collection_prefix: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Main processing workflow for date enrichment.
        Yields progress updates for real-time frontend tracking.
        """
        self._should_stop = False
        
        try:
            # Get batches to process
            if processing_mode == "single" and selected_batch:
                batches_to_process = [selected_batch]
            else:
                batches_to_process = await self.get_available_batches()
            
            if not batches_to_process:
                yield {
                    "status": "error",
                    "error": "No batches available for processing",
                    "overall_progress": 0,
                    "current_batch_progress": 0,
                    "documents_processed": 0,
                    "total_documents": 0,
                    "log_messages": ["ERROR: No batches found"]
                }
                return

            # Count total documents
            total_documents = 0
            for batch_name in batches_to_process:
                collection = self.source_db[batch_name]
                count = await collection.count_documents({})
                total_documents += count

            processed_documents = 0
            completed_batches = []
            
            yield {
                "status": "starting",
                "overall_progress": 0,
                "current_batch_progress": 0,
                "documents_processed": 0,
                "total_documents": total_documents,
                "current_batch": "",
                "current_document": "",
                "log_messages": [f"Starting processing of {len(batches_to_process)} batches with {total_documents} total documents"],
                "batch_summary": {
                    "completed_batches": [],
                    "current_batch": "",
                    "remaining_batches": batches_to_process
                }
            }

            # Process each batch
            for batch_index, batch_name in enumerate(batches_to_process):
                if self._should_stop:
                    break
                    
                # Extract batch number for target naming
                # Extract batch number from collection name (batch_1, batch_2, etc.)
                batch_number = batch_name.split('_')[-1] if '_' in batch_name else str(batch_index + 1)
                target_collection_name = f"{collection_prefix}_{batch_number}"
                
                yield {
                    "status": "processing",
                    "overall_progress": (processed_documents / total_documents) * 100,
                    "current_batch_progress": 0,
                    "documents_processed": processed_documents,
                    "total_documents": total_documents,
                    "current_batch": batch_name,
                    "current_document": "",
                    "log_messages": [f"Starting batch {batch_name} → {target_collection_name}"],
                    "batch_summary": {
                        "completed_batches": completed_batches,
                        "current_batch": batch_name,
                        "remaining_batches": batches_to_process[batch_index + 1:]
                    }
                }

                # Process this batch
                async for batch_progress in self._process_single_batch(
                    batch_name, 
                    target_collection_name,
                    processed_documents,
                    total_documents
                ):
                    if self._should_stop:
                        break
                    
                    # Update global progress
                    batch_progress["batch_summary"] = {
                        "completed_batches": completed_batches,
                        "current_batch": batch_name,
                        "remaining_batches": batches_to_process[batch_index + 1:]
                    }
                    
                    yield batch_progress
                    
                    # Update processed count
                    if "documents_processed_in_batch" in batch_progress:
                        processed_documents = batch_progress["documents_processed_in_batch"] + sum(
                            await self.target_db[f"{collection_prefix}_{b.split('_')[-1]}"].count_documents({})
                            for b in completed_batches
                        )

                # Mark batch as completed
                completed_batches.append(batch_name)
                
                # Get final count for this batch
                target_collection = self.target_db[target_collection_name]
                batch_processed_count = await target_collection.count_documents({})
                processed_documents += batch_processed_count
                
                yield {
                    "status": "processing",
                    "overall_progress": (processed_documents / total_documents) * 100,
                    "current_batch_progress": 100,
                    "documents_processed": processed_documents,
                    "total_documents": total_documents,
                    "current_batch": batch_name,
                    "current_document": "",
                    "log_messages": [f"Completed batch {batch_name}: {batch_processed_count} documents processed"],
                    "batch_summary": {
                        "completed_batches": completed_batches,
                        "current_batch": "",
                        "remaining_batches": batches_to_process[batch_index + 1:]
                    }
                }

            # Final completion message
            yield {
                "status": "completed",
                "overall_progress": 100,
                "current_batch_progress": 100,
                "documents_processed": processed_documents,
                "total_documents": total_documents,
                "current_batch": "",
                "current_document": "",
                "log_messages": [
                    "Processing completed successfully!",
                    f"Total processed: {processed_documents} documents",
                    "Target database: Date-Enriched-Batches",
                    f"Collections created: {len(completed_batches)} batches"
                ],
                "batch_summary": {
                    "completed_batches": completed_batches,
                    "current_batch": "",
                    "remaining_batches": []
                }
            }

        except Exception as e:
            yield {
                "status": "error",
                "error": str(e),
                "overall_progress": 0,
                "current_batch_progress": 0,
                "documents_processed": processed_documents,
                "total_documents": total_documents,
                "log_messages": [f"ERROR: {str(e)}"]
            }

    async def _process_single_batch(
        self, 
        source_batch_name: str, 
        target_collection_name: str,
        global_processed_count: int,
        global_total_count: int
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Process a single batch collection."""
        
        source_collection = self.source_db[source_batch_name]
        target_collection = self.target_db[target_collection_name]
        
        # Get total documents in this batch
        total_batch_docs = await source_collection.count_documents({})
        processed_batch_docs = 0
        
        # Process documents in chunks
        chunk_size = 50
        cursor = source_collection.find({})
        
        async for document in cursor:
            if self._should_stop:
                break
                
            try:
                # Process this document
                enriched_doc = await self._enrich_document_dates(document)
                
                # Insert into target collection
                await target_collection.insert_one(enriched_doc)
                
                processed_batch_docs += 1
                
                # Yield progress update every 10 documents or at completion
                if processed_batch_docs % 10 == 0 or processed_batch_docs == total_batch_docs:
                    batch_progress = (processed_batch_docs / total_batch_docs) * 100
                    global_progress = ((global_processed_count + processed_batch_docs) / global_total_count) * 100
                    
                    yield {
                        "status": "processing",
                        "overall_progress": global_progress,
                        "current_batch_progress": batch_progress,
                        "documents_processed": global_processed_count + processed_batch_docs,
                        "total_documents": global_total_count,
                        "current_batch": source_batch_name,
                        "current_document": enriched_doc.get("Statute_Name", "Unknown"),
                        "documents_processed_in_batch": processed_batch_docs,
                        "log_messages": [f"Processing {source_batch_name}: {processed_batch_docs}/{total_batch_docs} documents"]
                    }
                    
            except Exception as e:
                print(f"[ERROR] Failed to process document {document.get('_id')}: {str(e)}")
                continue

    async def _enrich_document_dates(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrich a single document with consolidated date information.
        This implements the core date processing logic.
        """
        
        # Create enriched document copy
        enriched_doc = document.copy()
        
        # Remove the original _id to get a new one in target collection
        if "_id" in enriched_doc:
            del enriched_doc["_id"]
        
        # Step 1: Consolidate existing date fields
        consolidated_date = None
        original_fields = []
        extraction_method = "field_merge"
        confidence_score = 0
        
        # Check for existing date fields
        date_field = document.get("Date")
        promulgation_date = document.get("Promulgation_Date") 
        
        if promulgation_date and promulgation_date != "Not Available":
            consolidated_date = promulgation_date
            original_fields.append("Promulgation_Date")
            confidence_score = 95
        elif date_field and date_field != "Not Available":
            consolidated_date = date_field
            original_fields.append("Date")
            confidence_score = 90
        
        # Step 2: If no valid date found, try AI extraction
        if not consolidated_date:
            ai_extracted_date = await self._extract_date_with_ai(document)
            if ai_extracted_date:
                consolidated_date = ai_extracted_date["date"]
                extraction_method = "ai_gpt4"
                confidence_score = ai_extracted_date["confidence"]
        
        # Step 3: Update the document
        enriched_doc["Date"] = consolidated_date or "Not Available"
        
        # Add metadata
        enriched_doc["date_metadata"] = {
            "extraction_method": extraction_method,
            "confidence_score": confidence_score,
            "processing_timestamp": datetime.utcnow().isoformat(),
            "original_fields": original_fields,
            "merged_date": consolidated_date,
            "ai_model": "gpt-4o" if extraction_method == "ai_gpt4" else None,
            "fallback_used": consolidated_date is None
        }
        
        enriched_doc["processing_status"] = "date_processed"
        enriched_doc["last_updated"] = datetime.utcnow().isoformat()
        
        return enriched_doc

    async def _extract_date_with_ai(self, document: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract date using Azure OpenAI GPT-4 from document sections.
        """
        
        if not self.ai_enabled:
            return await self._extract_date_with_patterns(document)
        
        try:
            sections = document.get("Sections", [])
            if not sections:
                return None
            
            # Prepare content for AI analysis
            statute_name = document.get("Statute_Name", "Unknown Statute")
            content_parts = []
            
            # Include preamble and first few sections
            for i, section in enumerate(sections[:5]):  # First 5 sections
                section_title = section.get("title", f"Section {i+1}")
                section_content = section.get("content", "")
                
                if section_content and len(section_content.strip()) > 10:
                    content_parts.append(f"{section_title}: {section_content}")
            
            if not content_parts:
                return None
            
            # Limit content length
            full_content = "\n\n".join(content_parts)
            if len(full_content) > self.processing_config["content_limit"]:
                full_content = full_content[:self.processing_config["content_limit"]] + "..."
            
            # Create AI prompt
            prompt = self._create_date_extraction_prompt(statute_name, full_content)
            
            # Call Azure OpenAI
            response = await self._call_azure_openai(prompt)
            
            if response:
                return self._parse_ai_response(response)
            
        except Exception as e:
            print(f"[ERROR] AI date extraction failed for {document.get('Statute_Name', 'Unknown')}: {str(e)}")
        
        # Fallback to pattern matching
        return await self._extract_date_with_patterns(document)

    def _create_date_extraction_prompt(self, statute_name: str, content: str) -> str:
        """Create a prompt for AI date extraction."""
        return f"""
You are a legal document analyst. Extract the most likely promulgation or enactment date from this Pakistani statute.

STATUTE NAME: {statute_name}

STATUTE CONTENT:
{content}

INSTRUCTIONS:
1. Look for the promulgation date, enactment date, or commencement date
2. Common phrases: "promulgated on", "enacted on", "commenced on", "passed on", "assented to on"
3. Return ONLY the date in DD-MMM-YYYY format (e.g., "17-Feb-1975")
4. If multiple dates exist, choose the promulgation/enactment date over commencement
5. If no date found, return "NO_DATE_FOUND"
6. Provide confidence score (0-100) and brief reasoning

RESPONSE FORMAT (JSON):
{{
    "date": "DD-MMM-YYYY or NO_DATE_FOUND",
    "confidence": 85,
    "reasoning": "Found promulgation date in preamble section",
    "source_location": "Preamble"
}}
"""

    async def _call_azure_openai(self, prompt: str) -> Optional[str]:
        """Call Azure OpenAI API with error handling and retries."""
        for attempt in range(self.processing_config["max_retries"]):
            try:
                response = await self.azure_client.chat.completions.create(
                    model=self.azure_openai_config["deployment_name"],
                    messages=[
                        {"role": "system", "content": "You are a precise legal document date extractor. Return only valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=self.processing_config["temperature"],
                    max_tokens=300
                )
                
                content = response.choices[0].message.content
                if content:
                    return content.strip()
                    
            except Exception as e:
                print(f"[ERROR] Azure OpenAI API call failed (attempt {attempt + 1}): {str(e)}")
                if attempt < self.processing_config["max_retries"] - 1:
                    await asyncio.sleep(self.processing_config["retry_delay"])
        
        return None

    def _parse_ai_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse AI response and extract date information."""
        try:
            # Try to parse as JSON
            if response.startswith('{') and response.endswith('}'):
                result = json.loads(response)
                
                date_str = result.get("date", "NO_DATE_FOUND")
                if date_str != "NO_DATE_FOUND":
                    return {
                        "date": date_str,
                        "confidence": min(result.get("confidence", 75), 95),  # Cap AI confidence at 95%
                        "source_section": result.get("source_location", "AI Analysis"),
                        "reasoning": result.get("reasoning", "Extracted by AI")
                    }
            
        except json.JSONDecodeError:
            # Try to extract date from plain text response
            date_patterns = [
                r'\b(\d{1,2}[-/]\w{3}[-/]\d{4})\b',
                r'\b(\d{1,2}[-/]\d{1,2}[-/]\d{4})\b',
                r'\b(\w{3,9}\s+\d{1,2},?\s+\d{4})\b'
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, response, re.IGNORECASE)
                if match:
                    return {
                        "date": match.group(1),
                        "confidence": 80,
                        "source_section": "AI Analysis",
                        "reasoning": "Extracted from AI response"
                    }
        
        return None

    async def _extract_date_with_patterns(self, document: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Fallback date extraction using regex patterns.
        """
        sections = document.get("Sections", [])
        if not sections:
            return None
        
        # Date patterns to search for
        date_patterns = [
            r'\b(\d{1,2}[-/]\w{3}[-/]\d{4})\b',  # 17-Feb-1975
            r'\b(\d{1,2}[-/]\d{1,2}[-/]\d{4})\b',  # 17/02/1975
            r'\b(\w{3,9}\s+\d{1,2},?\s+\d{4})\b',  # February 17, 1975
            r'\b(\d{4})\b'  # Just year as fallback
        ]
        
        # Keywords that indicate promulgation/enactment
        promulgation_keywords = [
            "promulgated", "enacted", "passed", "assented", "commenced",
            "notification", "gazette", "published"
        ]
        
        for section in sections[:3]:  # Check first 3 sections
            section_text = section.get("content", "").lower()
            
            # Look for promulgation context
            has_promulgation_context = any(keyword in section_text for keyword in promulgation_keywords)
            
            for pattern in date_patterns:
                matches = re.findall(pattern, section_text, re.IGNORECASE)
                if matches:
                    confidence = 85 if has_promulgation_context else 60
                    return {
                        "date": matches[0],
                        "confidence": confidence,
                        "source_section": section.get("title", "Unknown Section")
                    }
        
        return None

    async def stop_processing(self):
        """Stop the current processing operation."""
        self._should_stop = True

    async def export_results_to_excel(self) -> bytes:
        """Export processing results to Excel format."""
        try:
            # Get all target collections
            collections = await self.target_db.list_collection_names()
            
            # Create Excel writer
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                
                summary_data = []
                sheets_created = 0
                
                for collection_name in collections:
                    collection = self.target_db[collection_name]
                    
                    # Get sample documents
                    documents = []
                    async for doc in collection.find({}).limit(1000):  # Limit for performance
                        # Convert ObjectId to string for Excel
                        if "_id" in doc:
                            doc["_id"] = str(doc["_id"])
                        documents.append(doc)
                    
                    if documents:
                        # Create DataFrame
                        df = pd.json_normalize(documents)
                        
                        # Write to Excel sheet
                        sheet_name = collection_name[:31]  # Excel sheet name limit
                        df.to_excel(writer, sheet_name=sheet_name, index=False)
                        sheets_created += 1
                        
                        # Add to summary
                        summary_data.append({
                            "Collection": collection_name,
                            "Document_Count": len(documents),
                            "Date_Enriched": len([d for d in documents if d.get("Date") != "Not Available"]),
                            "AI_Extracted": len([d for d in documents if d.get("date_metadata", {}).get("extraction_method") == "ai_gpt4"]),
                            "Field_Merged": len([d for d in documents if d.get("date_metadata", {}).get("extraction_method") == "field_merge"])
                        })
                    else:
                        # Add empty collection to summary
                        summary_data.append({
                            "Collection": collection_name,
                            "Document_Count": 0,
                            "Date_Enriched": 0,
                            "AI_Extracted": 0,
                            "Field_Merged": 0
                        })
                
                # Always create a summary sheet to ensure at least one sheet exists
                if summary_data:
                    summary_df = pd.DataFrame(summary_data)
                    summary_df.to_excel(writer, sheet_name="Summary", index=False)
                    sheets_created += 1
                else:
                    # Create an empty summary sheet if no collections exist
                    empty_summary = pd.DataFrame({
                        "Status": ["No processing results available"],
                        "Message": ["Run Phase 4 processing first to generate results"]
                    })
                    empty_summary.to_excel(writer, sheet_name="Summary", index=False)
                    sheets_created += 1
                
                # If no sheets were created (shouldn't happen now), create a placeholder
                if sheets_created == 0:
                    placeholder_df = pd.DataFrame({
                        "Status": ["No data available"],
                        "Message": ["No processing results found"]
                    })
                    placeholder_df.to_excel(writer, sheet_name="NoData", index=False)
            
            output.seek(0)
            return output.getvalue()
            
        except Exception as e:
            print(f"[ERROR] Failed to export results: {str(e)}")
            raise e
