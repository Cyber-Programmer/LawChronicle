#!/usr/bin/env python3

import asyncio
import sys
import os

# Add the backend directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

async def debug_ai_method():
    """
    Debug the AI method step by step to find where the issue occurs
    """
    try:
        from backend.app.core.services.phase4_search_service import Phase4SearchService
        
        # Test text with clear dates
        text_with_dates = '''ACT VI OF 2020 SINDH INSTITUTE OF PHYSICAL MEDICINE AND REHABILITATION ACT, 2019 An Act to provide for the establishment of an institute known as the Sindh Institute of Physical Medicine and Rehabilitation [Gazette of Sindh Extraordinary, Part IV, 30th January, 2020] No. PASLEGIS-B-282019, dated 30.1.2020.--The Sindh Institute of Physical Medicine and Rehabilitation Bill, 2019 having been passed by the Provincial Assembly of Sindh on 19th December, 2019 and assented to by the Governor of Sindh on 22nd January, 2020 is hereby published as an Act of the Legislature of Sindh.'''
        
        # Create proper document structure like the API does
        test_document = {
            "Statute_Name": "Sindh Institute Of Physical Medicine And Rehabilitation Act 2019",
            "Sections_Sample": text_with_dates
        }
        
        print(f'🔍 Debugging AI extraction step by step...')
        
        # Initialize service
        search_service = Phase4SearchService()
        
        # Call the AI method with proper document structure
        print(f'🤖 Calling _extract_date_with_ai with document structure...')
        raw_result = await search_service._extract_date_with_ai(test_document)
        
        print(f'📡 Raw result type: {type(raw_result)}')
        print(f'📡 Raw result value: {raw_result}')
        
        # Test what happens when we try to use .get() on it
        if isinstance(raw_result, dict):
            print(f'✅ Result is dict - can use .get()')
            print(f'   Date: {raw_result.get("date", "N/A")}')
            print(f'   Confidence: {raw_result.get("confidence", "N/A")}')
        else:
            print(f'❌ Result is NOT dict - this is the problem!')
            print(f'   Trying to call .get() on {type(raw_result)} will fail')
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_ai_method())
