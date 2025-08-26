import os
import json
import asyncio
from typing import AsyncGenerator, Dict, Any, List, Optional
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
import re
from bson import ObjectId
import io
import pandas as pd


class Phase4Service:
    def __init__(self):
        # MongoDB connection
        self.mongo_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
        self.client = AsyncIOMotorClient(self.mongo_url)

        # Default source/target DBs
        self.source_db = self.client.get_database("Batched-Statutes")
        self.target_db = self.client.get_database("Date-Enriched-Batches")

        # Processing control
        self._should_stop = False

    async def get_available_batches(self, db_name: Optional[str] = None) -> List[str]:
        """Return a sorted list of batch collection names (batch_#) from the given DB."""
        db = self.client.get_database(db_name) if db_name else self.source_db
        names = await db.list_collection_names()
        # Filter names like batch_1, batch_2... and sort numerically
        batches = [n for n in names if re.match(r"^batch_\d+$", n)]
        def num_key(s: str) -> int:
            try:
                return int(s.split("_")[-1])
            except Exception:
                return 0
        batches.sort(key=num_key)
        return batches

    async def get_status(self) -> Dict[str, Any]:
        """Get current processing status."""
        try:
            # Get basic database connectivity status
            available_batches = await self.get_available_batches()
            
            # Get count of source documents
            total_documents = 0
            if available_batches:
                for batch in available_batches:
                    try:
                        count = await self.source_db[batch].count_documents({})
                        total_documents += count
                    except Exception:
                        pass
            
            # Get count of processed documents
            processed_documents = 0
            try:
                target_collections = await self.target_db.list_collection_names()
                for collection in target_collections:
                    if collection.startswith("batch"):
                        processed_documents += await self.target_db[collection].count_documents({})
            except Exception:
                pass
            
            return {
                "total_documents": total_documents,
                "processed_documents": processed_documents,
                "available_batches_count": len(available_batches)
            }
        except Exception as e:
            return {
                "error": str(e),
                "total_documents": 0,
                "processed_documents": 0,
                "available_batches_count": 0
            }

    async def process_date_enrichment(
        self,
        processing_mode: str = "all",
        selected_batch: Optional[str] = None,
        collection_prefix: str = "batch",
        batch_size: int = 50,
        dry_run: bool = False,
        generate_metadata: bool = False,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Main generator that processes batches and yields progress updates.

        processing_mode: 'all' or 'single'
        """
        try:
            # Determine which batches to process
            if processing_mode == "single" and selected_batch:
                batches_to_process = [selected_batch]
            else:
                batches_to_process = await self.get_available_batches()

            # Compute total documents across selected batches
            total_documents = 0
            for b in batches_to_process:
                total_documents += await self.source_db[b].count_documents({})

            processed_documents = 0
            completed_batches: List[str] = []

            # Iterate batches
            for batch_index, batch_name in enumerate(batches_to_process):
                if self._should_stop:
                    break

                batch_number = batch_name.split("_")[-1] if "_" in batch_name else str(batch_index + 1)
                target_collection_name = f"{collection_prefix}_{batch_number}"

                # Yield start message for this batch
                yield {
                    "status": "processing",
                    "overall_progress": (processed_documents / total_documents * 100) if total_documents else 0,
                    "current_batch_progress": 0,
                    "documents_processed": processed_documents,
                    "total_documents": total_documents,
                    "current_batch": batch_name,
                    "current_document": "",
                    "log_messages": [f"Starting batch {batch_name} → {target_collection_name}"],
                    "batch_summary": {
                        "completed_batches": completed_batches,
                        "current_batch": batch_name,
                        "remaining_batches": batches_to_process[batch_index + 1 :],
                    },
                }

                # Process the batch and stream progress
                async for batch_progress in self._process_single_batch(
                    source_batch_name=batch_name,
                    target_collection_name=target_collection_name,
                    global_processed_count=processed_documents,
                    global_total_count=total_documents,
                    chunk_size=batch_size,
                    dry_run=dry_run,
                    generate_metadata=generate_metadata,
                ):
                    if self._should_stop:
                        break
                    # Attach batch summary and yield
                    batch_progress["batch_summary"] = {
                        "completed_batches": completed_batches,
                        "current_batch": batch_name,
                        "remaining_batches": batches_to_process[batch_index + 1 :],
                    }
                    yield batch_progress

                # Mark completed and update processed_documents
                completed_batches.append(batch_name)
                # Recompute processed_documents by counting target collection docs
                try:
                    target_col = self.target_db[target_collection_name]
                    batch_processed_count = await target_col.count_documents({})
                except Exception:
                    batch_processed_count = 0
                processed_documents += batch_processed_count

                yield {
                    "status": "processing",
                    "overall_progress": (processed_documents / total_documents * 100) if total_documents else 0,
                    "current_batch_progress": 100,
                    "documents_processed": processed_documents,
                    "total_documents": total_documents,
                    "current_batch": batch_name,
                    "current_document": "",
                    "log_messages": [f"Completed batch {batch_name}: {batch_processed_count} documents processed"],
                    "batch_summary": {
                        "completed_batches": completed_batches,
                        "current_batch": "",
                        "remaining_batches": batches_to_process[batch_index + 1 :],
                    },
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
                    f"Collections created: {len(completed_batches)} batches",
                ],
                "batch_summary": {"completed_batches": completed_batches, "current_batch": "", "remaining_batches": []},
            }

        except Exception as e:
            yield {"status": "error", "error": str(e), "overall_progress": 0, "current_batch_progress": 0, "log_messages": [f"ERROR: {str(e)}"]}

    async def _process_single_batch(
        self,
        source_batch_name: str,
        target_collection_name: str,
        global_processed_count: int,
        global_total_count: int,
        chunk_size: int = 50,
        dry_run: bool = False,
        generate_metadata: bool = False,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Process documents in a single batch collection and yield progress updates."""
        # Ensure parameters are not None
        if chunk_size is None:
            chunk_size = 50
        if global_processed_count is None:
            global_processed_count = 0
        if global_total_count is None:
            global_total_count = 0
            
        source_collection = self.source_db[source_batch_name]
        target_collection = self.target_db[target_collection_name]

        total_batch_docs = await source_collection.count_documents({})
        processed_batch_docs = 0
        failures = 0
        written = 0
        samples: List[Dict[str, Any]] = []
        start_time = datetime.utcnow()

        buffer: List[Dict[str, Any]] = []
        cursor = source_collection.find({})
        async for document in cursor:
            buffer.append(document)
            if len(buffer) >= chunk_size:
                # process current buffer
                for doc in buffer:
                    if self._should_stop:
                        break
                    try:
                        enriched_doc = await self._enrich_document_dates(doc)
                        if not dry_run:
                            await target_collection.insert_one(enriched_doc)
                            written += 1
                        processed_batch_docs += 1
                        if len(samples) < 5:
                            samples.append({"_id": str(doc.get("_id")), "Date": enriched_doc.get("Date"), "date_metadata": enriched_doc.get("date_metadata")})

                        if processed_batch_docs % 10 == 0:
                            batch_progress = (processed_batch_docs / total_batch_docs * 100) if total_batch_docs else 0
                            global_progress = ((global_processed_count + processed_batch_docs) / global_total_count * 100) if global_total_count else 0
                            yield {
                                "status": "processing",
                                "overall_progress": global_progress,
                                "current_batch_progress": batch_progress,
                                "documents_processed": global_processed_count + processed_batch_docs,
                                "total_documents": global_total_count,
                                "current_batch": source_batch_name,
                                "current_document": enriched_doc.get("Statute_Name", "Unknown"),
                                "documents_processed_in_batch": processed_batch_docs,
                                "log_messages": [f"Processing {source_batch_name}: {processed_batch_docs}/{total_batch_docs} documents"],
                            }
                    except Exception as e:
                        failures += 1
                        # non-fatal, continue
                        print(f"[ERROR] Failed to process document {doc.get('_id')}: {str(e)}")
                buffer = []

        # process remaining buffer
        for doc in buffer:
            if self._should_stop:
                break
            try:
                enriched_doc = await self._enrich_document_dates(doc)
                if not dry_run:
                    await target_collection.insert_one(enriched_doc)
                    written += 1
                processed_batch_docs += 1
                if len(samples) < 5:
                    samples.append({"_id": str(doc.get("_id")), "Date": enriched_doc.get("Date"), "date_metadata": enriched_doc.get("date_metadata")})

                if processed_batch_docs % 10 == 0 or processed_batch_docs == total_batch_docs:
                    batch_progress = (processed_batch_docs / total_batch_docs * 100) if total_batch_docs else 0
                    global_progress = ((global_processed_count + processed_batch_docs) / global_total_count * 100) if global_total_count else 0
                    yield {
                        "status": "processing",
                        "overall_progress": global_progress,
                        "current_batch_progress": batch_progress,
                        "documents_processed": global_processed_count + processed_batch_docs,
                        "total_documents": global_total_count,
                        "current_batch": source_batch_name,
                        "current_document": enriched_doc.get("Statute_Name", "Unknown"),
                        "documents_processed_in_batch": processed_batch_docs,
                        "log_messages": [f"Processing {source_batch_name}: {processed_batch_docs}/{total_batch_docs} documents"],
                    }
            except Exception as e:
                failures += 1
                print(f"[ERROR] Failed to process document {doc.get('_id')}: {str(e)}")

        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()

        # Write metadata if requested
        if generate_metadata:
            metadata = {
                "batch": source_batch_name,
                "target_collection": target_collection_name,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration,
                "total_documents": total_batch_docs,
                "processed": processed_batch_docs,
                "written": written,
                "failures": failures,
                "samples": samples,
                "date_format": "DD-MMM-YYYY",
            }

            try:
                metadata_dir = os.path.join(os.path.dirname(__file__), '../../api/metadata')
                os.makedirs(metadata_dir, exist_ok=True)
                
                # Use unified naming convention: {operation}-{database}-{collection}-{date}.{ext}
                date_str = datetime.utcnow().strftime('%Y-%m-%d')
                operation = "merge"
                collection = target_collection_name.lower().replace("_", "-")
                filename = f"{operation}-date-enriched-{collection}-{date_str}.json"
                filepath = os.path.join(metadata_dir, filename)
                tmp_filepath = filepath + ".tmp"
                # Write atomically: write to temp file then replace
                with open(tmp_filepath, "w", encoding="utf-8") as mf:
                    json.dump(metadata, mf, ensure_ascii=False, indent=2)
                    mf.flush()
                    try:
                        os.fsync(mf.fileno())
                    except Exception:
                        # os.fsync may not be available on all platforms or in some contexts
                        pass
                os.replace(tmp_filepath, filepath)
            except Exception as e:
                print(f"[ERROR] Failed to write metadata file: {str(e)}")

            try:
                await self.target_db["phase4_metadata"].insert_one(metadata)
            except Exception as e:
                print(f"[ERROR] Failed to insert metadata into DB: {str(e)}")

        # Final batch summary yield
        yield {
            "status": "batch_completed",
            "overall_progress": ((global_processed_count + processed_batch_docs) / global_total_count * 100) if global_total_count else 0,
            "current_batch_progress": 100,
            "documents_processed": global_processed_count + processed_batch_docs,
            "total_documents": global_total_count,
            "current_batch": source_batch_name,
            "current_document": "",
            "log_messages": [f"Finished processing batch {source_batch_name}"],
            "batch_summary": {"processed": processed_batch_docs, "written": written, "failures": failures},
        }

    async def _enrich_document_dates(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich and normalize date fields for a single document.

        Normalizes to DD-MMM-YYYY (example: 05-Aug-2025) when a date can be parsed.
        Uses the same logic as the reference parse_dates.py implementation.
        """
        enriched_doc = document.copy()
        if "_id" in enriched_doc:
            del enriched_doc["_id"]

        consolidated_date = None
        original_fields: List[str] = []
        extraction_method = "field_merge"
        confidence_score = 0

        # Get the raw field values
        date_field = document.get("Date")
        promulgation_date = document.get("Promulgation_Date")

        # Use the same logic as reference: check both fields and prefer Date over Promulgation_Date
        # Reference logic: date_str = doc.get("Date") or doc.get("Promulgation_Date")
        if self._is_filled(date_field):
            consolidated_date = date_field
            original_fields.append("Date")
            confidence_score = 90
        elif self._is_filled(promulgation_date):
            consolidated_date = promulgation_date
            original_fields.append("Promulgation_Date")
            confidence_score = 95

        # Skip pattern extraction - only merge existing Date and Promulgation_Date fields
        # If no valid date found in either field, leave Date as empty string

        # Try to parse and normalize the consolidated date
        normalized = None
        if consolidated_date:
            parsed = self._parse_date_string(str(consolidated_date))
            if parsed:
                # Use the same format as reference: "%d-%b-%Y"
                normalized = parsed.strftime("%d-%b-%Y")
                extraction_method = extraction_method  # Keep the method that found it
            else:
                # If we found a date string but couldn't parse it, still record the attempt
                extraction_method = "parse_failed"
                confidence_score = 10

        # Set the final Date field - use empty string for missing like reference, not "Not Available"
        enriched_doc["Date"] = normalized or ""

        # Remove Promulgation_Date field like in reference implementation
        if "Promulgation_Date" in enriched_doc:
            del enriched_doc["Promulgation_Date"]

        enriched_doc["date_metadata"] = {
            "extraction_method": extraction_method,
            "confidence_score": confidence_score,
            "processing_timestamp": datetime.utcnow().isoformat(),
            "original_fields": original_fields,
            "merged_date": consolidated_date,
            "normalized_date": normalized,
        }

        enriched_doc["processing_status"] = "date_processed"
        return enriched_doc

    def _is_filled(self, val: Any) -> bool:
        """Check if a value is filled (not None, not empty string, not 'Not Available')."""
        if val is None:
            return False
        val_str = str(val).strip()
        return val_str != '' and val_str.lower() not in ['not available', 'null', 'none', 'n/a']

    def _parse_date_string(self, s: str) -> Optional[datetime]:
        """Attempt to parse a date string using dateutil parser (more flexible like reference)."""
        if not s or not s.strip():
            return None
        
        try:
            # First try dateutil parser with fuzzy=True (like reference implementation)
            from dateutil import parser as date_parser
            return date_parser.parse(s.strip(), fuzzy=True)
        except Exception:
            pass
        
        # Fallback to our manual parsing
        s = s.strip()
        formats = ["%Y-%m-%d", "%d-%b-%Y", "%d-%m-%Y", "%d/%m/%Y", "%B %d, %Y", "%d %B %Y", "%Y/%m/%d"]
        for fmt in formats:
            try:
                return datetime.strptime(s, fmt)
            except Exception:
                continue

        # Try to extract numeric components: e.g., 12 Jan 2025 or 12-Jan-2025
        m = re.search(r"(\d{1,2})\D+(\w{3,9})\D+(\d{4})", s)
        if m:
            d, mon, y = m.groups()
            try:
                return datetime.strptime(f"{d} {mon} {y}", "%d %b %Y")
            except Exception:
                try:
                    return datetime.strptime(f"{d} {mon} {y}", "%d %B %Y")
                except Exception:
                    return None
        return None

    def _extract_date_with_patterns(self, document: Dict[str, Any]) -> Optional[str]:
        """Look for date-like strings in document fields using broader patterns.
        
        Based on reference implementation approach but expanded to handle more cases.
        """
        # Get all string fields from the document, including nested content
        text_fields = []
        
        # Add main string fields
        for k, v in document.items():
            if isinstance(v, str) and len(v.strip()) > 0:
                text_fields.append(v)
        
        # Also check in Sections content if present (common in legal documents)
        sections = document.get("Sections", [])
        if isinstance(sections, list):
            for section in sections[:5]:  # Check first 5 sections only for performance
                if isinstance(section, dict):
                    content = section.get("content", "")
                    title = section.get("title", "")
                    if isinstance(content, str) and len(content.strip()) > 0:
                        text_fields.append(content[:500])  # Limit length for performance
                    if isinstance(title, str) and len(title.strip()) > 0:
                        text_fields.append(title)
        
        # More comprehensive date patterns
        date_patterns = [
            # DD-MMM-YYYY (17-Feb-1975)
            r'\b(\d{1,2}[-/]\w{3}[-/]\d{4})\b',
            # DD/MM/YYYY or DD-MM-YYYY
            r'\b(\d{1,2}[-/]\d{1,2}[-/]\d{4})\b',
            # Month DD, YYYY (February 17, 1975)
            r'\b(\w{3,9}\s+\d{1,2},?\s+\d{4})\b',
            # DD Month YYYY (17 February 1975)
            r'\b(\d{1,2}\s+\w{3,9}\s+\d{4})\b',
            # YYYY-MM-DD (1975-02-17)
            r'\b(\d{4}[-/]\d{1,2}[-/]\d{1,2})\b',
            # Just year as very last resort (but only if it looks reasonable)
            r'\b(19\d{2}|20[0-2]\d)\b'
        ]
        
        # Keywords that suggest this might be a promulgation/enactment date
        date_context_keywords = [
            'promulgate', 'enact', 'pass', 'assent', 'commence', 'effect',
            'notification', 'gazette', 'publish', 'date', 'on', 'dated'
        ]
        
        for text in text_fields:
            text_lower = text.lower()
            
            # Check if this text has date-related context
            has_date_context = any(keyword in text_lower for keyword in date_context_keywords)
            
            # Try each pattern
            for i, pattern in enumerate(date_patterns):
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    # If we have date context, prefer this match
                    # Otherwise, only return if it's a well-formed date (not just a year)
                    if has_date_context or i < len(date_patterns) - 1:  # Not just the year pattern
                        return matches[0]
        
        return None

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
