#!/usr/bin/env python3
"""
Check document content to see if sections are empty
"""

import asyncio
import sys
import os

# Add the backend directory to the Python path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

from app.core.services.phase4_search_service import Phase4SearchService

async def check_document_content():
    """Check if documents have sufficient content for AI processing"""
    
    print("📄 Checking Document Content...")
    
    try:
        service = Phase4SearchService()
        collections = await service.get_available_collections()
        
        # Check documents from multiple collections
        for collection_name in collections[:3]:
            print(f"\n📁 Checking collection: {collection_name}")
            collection = service.source_db[collection_name]
            
            missing_query = {
                "$or": [
                    {"Date": {"$in": ["", None]}},
                    {"Date": {"$exists": False}}
                ]
            }
            
            cursor = collection.find(missing_query).limit(3)
            
            doc_count = 0
            async for doc in cursor:
                doc_count += 1
                statute_name = doc.get("Statute_Name", "")
                sections = doc.get("Sections", [])
                
                print(f"\n   📄 Document {doc_count}: {statute_name}")
                print(f"      - Total sections: {len(sections)}")
                
                if len(sections) > 0:
                    # Check first few sections
                    for i, section in enumerate(sections[:3]):
                        section_text = section.get("Section_Text", "")
                        print(f"      - Section {i+1} length: {len(section_text)}")
                        if len(section_text) > 0:
                            print(f"      - Section {i+1} preview: '{section_text[:100]}...'")
                        else:
                            print(f"      - Section {i+1}: EMPTY")
                
                # Check the combined sections text (as used by AI)
                sections_sample = " ".join([
                    section.get("Section_Text", "") 
                    for section in sections[:3]
                ])[:2000]
                
                print(f"      - Combined sections length: {len(sections_sample)}")
                if len(sections_sample) > 20:
                    print(f"      - Combined preview: '{sections_sample[:150]}...'")
                else:
                    print(f"      - Combined text: '{sections_sample}'")
                
                # Test AI extraction on a document with good content
                if len(sections_sample) > 100:
                    print(f"      - Testing AI extraction on this document...")
                    doc_dict = {
                        "Collection": collection_name,
                        "Document_ID": str(doc["_id"]),
                        "Statute_Name": statute_name,
                        "Province": doc.get("Province", ""),
                        "Sections_Sample": sections_sample
                    }
                    
                    try:
                        extracted_info = await service._extract_date_with_ai(doc_dict)
                        print(f"      - AI Result: {extracted_info}")
                    except Exception as e:
                        print(f"      - AI Error: {e}")
                
                if doc_count >= 2:  # Check only 2 docs per collection
                    break
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_document_content())
