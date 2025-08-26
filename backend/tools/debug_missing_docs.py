#!/usr/bin/env python3

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import sys
import os

# Add the backend directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

async def debug_missing_docs():
    """
    Debug the missing docs collection process exactly like the API does
    """
    try:
        # Connect to MongoDB
        client = AsyncIOMotorClient("mongodb://localhost:27017")
        db = client["Date-Enriched-Batches"]
        
        # Use the same logic as the API
        collections = ["batch_9"]  # Test with batch_9 only
        max_docs = 3  # Limit to 3 for debugging
        
        missing_docs = []
        total_missing_count = 0
        
        # First, count total missing documents across all collections
        for collection_name in collections:
            collection = db[collection_name]
            missing_query = {
                "$or": [
                    {"Date": {"$in": ["", None]}},
                    {"Date": {"$exists": False}}
                ]
            }
            count = await collection.count_documents(missing_query)
            total_missing_count += count
            print(f"[DEBUG] {collection_name}: {count} missing documents")

        print(f"[DEBUG] Total missing documents to process: {total_missing_count}")
        
        # If max_docs is specified, limit the processing
        if max_docs is not None:
            total_missing_count = min(total_missing_count, max_docs)
            print(f"[DEBUG] Limited to {max_docs} documents for processing")
        
        # Collect documents for processing (exactly like API)
        collected_count = 0
        for collection_name in collections:
            if max_docs and collected_count >= max_docs:
                break
                
            collection = db[collection_name]
            missing_query = {
                "$or": [
                    {"Date": {"$in": ["", None]}},
                    {"Date": {"$exists": False}}
                ]
            }
            
            cursor = collection.find(missing_query)
            
            # Apply limit only if max_docs is specified and we haven't exceeded it
            if max_docs:
                remaining_docs = max_docs - collected_count
                if remaining_docs > 0:
                    cursor = cursor.limit(remaining_docs)
                    print(f"[DEBUG] Limiting cursor to {remaining_docs} docs")
                else:
                    break  # No more docs needed
            
            async for doc in cursor:
                print(f"[DEBUG] Processing document: {doc['_id']}")
                print(f"[DEBUG] Statute_Name: {doc.get('Statute_Name', 'N/A')}")
                print(f"[DEBUG] Date field: '{doc.get('Date', 'NOT_PRESENT')}'")
                print(f"[DEBUG] Number of sections: {len(doc.get('Sections', []))}")
                
                # Check sections content
                sections = doc.get("Sections", [])
                if sections:
                    first_section = sections[0]
                    statute_text = first_section.get("Statute", first_section.get("Section_Text", ""))
                    print(f"[DEBUG] First section text length: {len(statute_text)}")
                    print(f"[DEBUG] First section preview: {statute_text[:100]}...")
                
                missing_docs.append({
                    "Collection": collection_name,
                    "Document_ID": str(doc["_id"]),
                    "Statute_Name": doc.get("Statute_Name", ""),
                    "Province": doc.get("Province", ""),
                    "Sections_Sample": " ".join([
                        section.get("Statute", section.get("Section_Text", ""))  # Try both field names
                        for section in doc.get("Sections", [])[:3]
                    ])[:2000]
                })
                collected_count += 1
                
                if max_docs and collected_count >= max_docs:
                    break
        
        print(f"[DEBUG] Collected {len(missing_docs)} documents for AI processing")
        
        # Show what we collected
        for i, doc in enumerate(missing_docs):
            print(f"[DEBUG] Doc {i+1}:")
            print(f"  - Collection: {doc['Collection']}")
            print(f"  - ID: {doc['Document_ID']}")
            print(f"  - Statute_Name: {doc['Statute_Name']}")
            print(f"  - Sample text length: {len(doc['Sections_Sample'])}")
            print(f"  - Sample preview: {doc['Sections_Sample'][:100]}...")
            print()
        
        await client.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_missing_docs())
