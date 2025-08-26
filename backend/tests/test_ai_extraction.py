#!/usr/bin/env python3
"""
Test the AI extraction method directly to see where it's failing
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from backend.app.core.services.phase4_search_service import Phase4SearchService

async def test_ai_extraction():
    """Test AI extraction directly"""
    
    try:
        service = Phase4SearchService()
        
        # Test document similar to what our collection creates
        test_doc = {
            "Collection": "batch_5",
            "Document_ID": "test123",
            "Statute_Name": "Test Act 1973",
            "Province": "Federal", 
            "Sections_Sample": "TEST ACT 1973 [Dated: 15th March, 1973] This act was published in the Gazette of Pakistan..."
        }
        
        print("🔧 Testing AI Extraction Directly")
        print("=" * 50)
        print(f"📄 Test Document:")
        print(f"   Statute: {test_doc['Statute_Name']}")
        print(f"   Sample: {test_doc['Sections_Sample'][:100]}...")
        print()
        
        print("🤖 Calling AI extraction...")
        
        # Let's also test the AI response directly to see what's happening
        try:
            # Call AI directly to see raw response
            test_prompt = """
            Extract the enactment or promulgation date from this Pakistani statute.
            
            Statute Name: Test Act 1973
            
            Statute Text: TEST ACT 1973 [Dated: 15th March, 1973] This act was published in the Gazette of Pakistan...
            
            Look for:
            - Dates in brackets like [4th March, 2016]
            - "Dated" followed by a date
            - "Published in Gazette" with dates
            - Any other date references indicating when this law was enacted
            
            Respond in JSON format:
            {
                "date": "DD-MMM-YYYY format or empty string",
                "confidence": 0-100,
                "reasoning": "Brief explanation of how date was found",
                "method": "bracket|dated|gazette|other"
            }
            """
            
            print("🔄 Testing direct Azure OpenAI call...")
            response = await service.azure_client.chat.completions.create(
                model="gpt-4o",  # or whatever model is configured
                messages=[
                    {"role": "system", "content": "You are an expert at extracting dates from Pakistani legal documents."},
                    {"role": "user", "content": test_prompt}
                ],
                max_tokens=200,
                temperature=0.1
            )
            
            raw_response = response.choices[0].message.content.strip()
            print(f"📝 Raw AI Response:")
            print(f"   '{raw_response}'")
            print()
            
            # Try to parse it
            try:
                import json
                parsed = json.loads(raw_response)
                print("✅ JSON parsing succeeded:")
                print(f"   {parsed}")
            except json.JSONDecodeError as e:
                print(f"❌ JSON parsing failed: {e}")
                print(f"   Response type: {type(raw_response)}")
                print(f"   Response length: {len(raw_response)}")
            
        except Exception as ai_error:
            print(f"❌ Direct AI call failed: {ai_error}")
        
        result = await service._extract_date_with_ai(test_doc)
        
        print("🎯 AI Result:")
        print(f"   Date: {result.get('date', 'None')}")
        print(f"   Confidence: {result.get('confidence', 0)}")
        print(f"   Method: {result.get('method', 'Unknown')}")
        print(f"   Reasoning: {result.get('reasoning', 'No reasoning')}")
        
        if result.get('date'):
            print("✅ SUCCESS: AI extraction worked!")
        else:
            print("❌ ISSUE: AI extraction returned no date")
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_ai_extraction())
