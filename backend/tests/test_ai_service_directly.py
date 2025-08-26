#!/usr/bin/env python3

import asyncio
import sys
import os

# Add the backend directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from backend.app.core.services.phase4_search_service import Phase4SearchService

async def test_ai_service_directly():
    """
    Test the AI service method directly with the same documents the API collects
    """
    try:
        # Create the same documents the API would collect
        test_docs = [
            {
                "Collection": "batch_9",
                "Document_ID": "68a4458f69f1d1cc1452528b",
                "Statute_Name": "Sindh Institute Of Physical Medicine And Rehabilitation Act 2019",
                "Province": "",
                "Sections_Sample": "ACT VI OF 2020 SINDH INSTITUTE OF PHYSICAL MEDICINE AND REHABILITATION ACT, 2019 An Act to provide for the establishment of the Sindh Institute of Physical Medicine and Rehabilitation..."[:2000]
            },
            {
                "Collection": "batch_9", 
                "Document_ID": "68a4458f69f1d1cc14525292",
                "Statute_Name": "Sindh Irrigation And Drainage Authority Ordinance 1997",
                "Province": "",
                "Sections_Sample": "SINDH IRRIGATION AND DRAINAGE AUTHORITY ORDINANCE, 1997 An Ordinance to provide for the establishment of the Sindh Irrigation and Drainage Authority..."[:2000]
            },
            {
                "Collection": "batch_9",
                "Document_ID": "68a4458f69f1d1cc14525294", 
                "Statute_Name": "Sindh Katchi Abadis (Amendment) Act 2009",
                "Province": "",
                "Sections_Sample": "ACT III OF 2016 SINDH KATCHI ABADIS (AMENDMENT) ACT, 2009 An Act to amend the Sindh Katchi Abadis Act..."[:2000]
            }
        ]
        
        print(f"🔍 Testing AI service with {len(test_docs)} documents...")
        
        # Initialize the service
        search_service = Phase4SearchService()
        
        print(f"🤖 Starting AI search...")
        
        results = []
        async for result in search_service.search_dates_with_ai(test_docs):
            print(f"📡 Received result: {result}")
            
            if result["status"] == "processing":
                print(f"   📊 Progress: {result.get('progress', 'N/A')}%")
                print(f"   📝 Statute: {result.get('statute_name', 'N/A')}")
                print(f"   📅 Date Found: {result.get('date_found', 'N/A')}")
                results.append(result)
                
            elif result["status"] == "completed":
                print(f"✅ AI Search completed!")
                print(f"   📈 Total processed: {result.get('total_processed', 'N/A')}")
                print(f"   📊 Success rate: {result.get('success_rate', 'N/A')}")
                break
                
            elif result["status"] == "error":
                print(f"❌ Error: {result.get('message', 'Unknown error')}")
                break
        
        print(f"\n📈 Final Results: {len(results)} documents processed")
        for i, result in enumerate(results):
            print(f"  {i+1}. {result.get('statute_name', 'N/A')}: {result.get('date_found', 'N/A')}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_ai_service_directly())
