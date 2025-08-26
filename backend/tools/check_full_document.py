#!/usr/bin/env python3

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

async def check_full_document():
    """
    Check the full document content to see if date information exists
    """
    try:
        client = AsyncIOMotorClient('mongodb://localhost:27017')
        db = client['Date-Enriched-Batches']
        collection = db['batch_9']
        
        # Get the exact document the AI processed
        doc_id = ObjectId('68a4458f69f1d1cc1452528b')
        doc = await collection.find_one({'_id': doc_id})
        
        if doc:
            print(f'📝 Statute Name: {doc.get("Statute_Name", "N/A")}')
            print(f'📅 Current Date: "{doc.get("Date", "EMPTY")}"')
            print(f'📊 Number of sections: {len(doc.get("Sections", []))}')
            
            # Check each section for date information
            sections = doc.get('Sections', [])
            date_keywords = ['dated', 'gazette', '2019', '2020', 'assent', 'passed', 'published']
            
            for i, section in enumerate(sections):
                statute_text = section.get('Statute', section.get('Section_Text', ''))
                
                # Check if this section contains date-related keywords
                text_lower = statute_text.lower()
                contains_date_info = any(keyword in text_lower for keyword in date_keywords)
                
                if contains_date_info:
                    print(f'\n📅 Section {i+1} contains potential date info:')
                    print(f'   Section name: {section.get("Section", "N/A")}')
                    print(f'   Text length: {len(statute_text)} characters')
                    print(f'   Text: {statute_text[:800]}...')
            
            # Also check if there's date info in the first 3 sections (what AI got)
            first_3_combined = " ".join([
                section.get("Statute", section.get("Section_Text", ""))
                for section in sections[:3]
            ])[:2000]
            
            print(f'\n🔍 AI received (first 3 sections, 2000 chars):')
            print(f'   Combined text length: {len(first_3_combined)}')
            
            # Check if the sample contains date info
            sample_lower = first_3_combined.lower()
            sample_has_dates = any(keyword in sample_lower for keyword in date_keywords)
            print(f'   Contains date keywords: {sample_has_dates}')
            
            if sample_has_dates:
                print(f'   Sample text: {first_3_combined[:500]}...')
            else:
                print('   ❌ Sample text does NOT contain obvious date keywords')
                print(f'   Sample preview: {first_3_combined[:300]}...')
        else:
            print('❌ Document not found')
        
        await client.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_full_document())
