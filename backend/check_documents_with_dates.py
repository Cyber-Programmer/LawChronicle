#!/usr/bin/env python3
"""
Check if documents with dates have section content
"""

import asyncio
import sys
import os

# Add the backend directory to the Python path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

from app.core.services.phase4_search_service import Phase4SearchService

async def check_documents_with_dates():
    """Check if documents with dates have section content"""
    
    print("📅 Checking Documents WITH Dates...")
    
    try:
        service = Phase4SearchService()
        collections = await service.get_available_collections()
        
        collection_name = collections[0]  # Check first collection
        collection = service.source_db[collection_name]
        
        # Query for documents WITH dates
        has_date_query = {
            "Date": {"$nin": ["", None]},
            "$and": [{"Date": {"$exists": True}}]
        }
        
        print(f"📁 Checking collection: {collection_name}")
        cursor = collection.find(has_date_query).limit(3)
        
        doc_count = 0
        async for doc in cursor:
            doc_count += 1
            statute_name = doc.get("Statute_Name", "")
            date_field = doc.get("Date", "")
            sections = doc.get("Sections", [])
            
            print(f"\n   📄 Document {doc_count}: {statute_name}")
            print(f"      - Date: {date_field}")
            print(f"      - Total sections: {len(sections)}")
            
            if len(sections) > 0:
                # Check first few sections
                for i, section in enumerate(sections[:3]):
                    section_text = section.get("Section_Text", "")
                    print(f"      - Section {i+1} length: {len(section_text)}")
                    if len(section_text) > 50:
                        print(f"      - Section {i+1} preview: '{section_text[:100]}...'")
                    elif len(section_text) > 0:
                        print(f"      - Section {i+1}: '{section_text}'")
                    else:
                        print(f"      - Section {i+1}: EMPTY")
        
        print(f"\n📊 Now checking the ACTUAL document structure...")
        
        # Let's also check the raw document structure
        cursor = collection.find({}).limit(1)
        async for doc in cursor:
            print(f"\n🔍 Raw document structure:")
            print(f"   - Keys: {list(doc.keys())}")
            if "Sections" in doc:
                sections = doc["Sections"]
                if len(sections) > 0:
                    print(f"   - First section keys: {list(sections[0].keys())}")
                    print(f"   - First section content: {sections[0]}")
            break
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_documents_with_dates())
