#!/usr/bin/env python3

import asyncio
import sys
import os

# Add the backend directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from backend.app.core.services.phase4_search_service import Phase4SearchService

async def test_ai_with_clear_dates():
    """
    Test AI extraction with text that clearly contains dates
    """
    try:
        # The exact text that contains multiple dates from the document
        text_with_dates = '''ACT VI OF 2020 SINDH INSTITUTE OF PHYSICAL MEDICINE AND REHABILITATION ACT, 2019 An Act to provide for the establishment of an institute known as the Sindh Institute of Physical Medicine and Rehabilitation [Gazette of Sindh Extraordinary, Part IV, 30th January, 2020] No. PASLEGIS-B-282019, dated 30.1.2020.--The Sindh Institute of Physical Medicine and Rehabilitation Bill, 2019 having been passed by the Provincial Assembly of Sindh on 19th December, 2019 and assented to by the Governor of Sindh on 22nd January, 2020 is hereby published as an Act of the Legislature of Sindh.'''
        
        print(f'🧪 Testing AI with text containing multiple clear dates:')
        print(f'📅 Expected dates: 30.1.2020, 30th January 2020, 19th December 2019, 22nd January 2020')
        print(f'📝 Text: {text_with_dates[:150]}...')
        
        search_service = Phase4SearchService()
        result = await search_service._extract_date_with_ai(text_with_dates)
        
        print(f'\n🤖 AI Result: {result}')
        if result:
            print(f'   📅 Date: {result.get("date", "N/A")}')
            print(f'   🎯 Confidence: {result.get("confidence", "N/A")}')
            print(f'   📋 Method: {result.get("method", "N/A")}')
            print(f'   💭 Reasoning: {result.get("reasoning", "N/A")}')
            
            if result.get("date") and result.get("date") != "":
                print(f'✅ SUCCESS: AI extracted date successfully!')
            else:
                print(f'❌ FAILURE: AI did not extract any date')
        else:
            print(f'❌ FAILURE: AI returned None/empty result')
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_ai_with_clear_dates())
