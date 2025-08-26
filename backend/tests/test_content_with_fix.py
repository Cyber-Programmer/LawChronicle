#!/usr/bin/env python3
"""
Test document content after field fix - check if our changes are working
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from motor.motor_asyncio import AsyncIOMotorClient

async def test_document_content_with_fix():
    """Test if documents now have content with our field fix"""
    
    try:
        # Connect to database
        client = AsyncIOMotorClient("mongodb://localhost:27017")
        db = client["Date-Enriched-Batches"]
        collection = db["5batch"]
        
        print("🔧 Testing Document Content with Field Fix")
        print("=" * 60)
        
        # Find documents without Date_Enacted
        query = {
            "$or": [
                {"Date_Enacted": {"$exists": False}},
                {"Date_Enacted": None},
                {"Date_Enacted": ""}
            ]
        }
        
        print("📋 Finding documents without Date_Enacted...")
        cursor = collection.find(query).limit(3)
        
        async for doc in cursor:
            print(f"\n📄 Document: {doc.get('Statute_Name', 'Unknown')[:60]}...")
            print(f"   🆔 ID: {str(doc['_id'])}")
            
            sections = doc.get("Sections", [])
            print(f"   📊 Total sections: {len(sections)}")
            
            if sections:
                # Test our fix - try both fields
                for i, section in enumerate(sections[:3]):  # Check first 3 sections
                    statute_text = section.get("Statute", "")
                    section_text = section.get("Section_Text", "")
                    
                    print(f"\n   📄 Section {i+1}:")
                    print(f"      📋 Statute field length: {len(statute_text)}")
                    print(f"      📋 Section_Text field length: {len(section_text)}")
                    
                    # Show preview of actual content
                    if statute_text:
                        print(f"      📄 Statute preview: {statute_text[:100]}...")
                    if section_text:
                        print(f"      📄 Section_Text preview: {section_text[:100]}...")
                    
                    # This is what our fix now uses
                    combined_text = section.get("Statute", section.get("Section_Text", ""))
                    print(f"      ✅ Combined text length: {len(combined_text)}")
                    
                    if combined_text:
                        print(f"      📄 Combined preview: {combined_text[:100]}...")
                        break
                
                # Test the combined sections approach used in the API
                sections_sample = " ".join([
                    section.get("Statute", section.get("Section_Text", ""))
                    for section in sections[:3]
                ])[:2000]
                
                print(f"\n   🎯 Combined sections sample length: {len(sections_sample)}")
                if sections_sample:
                    print(f"   📄 Sample preview: {sections_sample[:150]}...")
                    print("\n   ✅ SUCCESS: Document has text content after fix!")
                else:
                    print("\n   ❌ ISSUE: Still no text content even after fix")
            else:
                print("   ❌ No sections found")
        
        client.close()
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_document_content_with_fix())
