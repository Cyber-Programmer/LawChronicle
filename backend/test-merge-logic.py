#!/usr/bin/env python3
"""Test script to verify the Phase 4 date merge logic"""

import asyncio
import os
import sys
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from core.services.phase4_service import Phase4Service

async def test_merge_logic():
    """Test the date merge logic with sample documents"""
    
    # Sample test documents representing different scenarios
    test_docs = [
        {
            "_id": "test1",
            "Date": "01-Jan-2020",
            "Promulgation_Date": "02-Feb-2020",
            "Title": "Test with both dates - Date should be preferred"
        },
        {
            "_id": "test2", 
            "Date": "",
            "Promulgation_Date": "05-May-2021",
            "Title": "Test with empty Date, filled Promulgation_Date"
        },
        {
            "_id": "test3",
            "Date": "10-Oct-2022",
            "Title": "Test with only Date field"
        },
        {
            "_id": "test4",
            "Promulgation_Date": "15-Dec-2023",
            "Title": "Test with only Promulgation_Date field"
        },
        {
            "_id": "test5",
            "Date": "",
            "Promulgation_Date": "",
            "Title": "Test with both fields empty"
        },
        {
            "_id": "test6",
            "Title": "Test with no date fields at all"
        }
    ]
    
    # Initialize the service (it connects to DB automatically)
    service = Phase4Service()
    
    print("Testing Phase 4 date merge logic:")
    print("=" * 60)
    
    for i, doc in enumerate(test_docs, 1):
        print(f"\nTest {i}: {doc.get('Title', 'Untitled')}")
        print(f"Input - Date: '{doc.get('Date', 'NOT_SET')}', Promulgation_Date: '{doc.get('Promulgation_Date', 'NOT_SET')}'")
        
        try:
            result = await service._enrich_document_dates(doc)
            output_date = result.get('Date', 'NOT_SET')
            metadata = result.get('date_metadata', {})
            
            print(f"Output - Date: '{output_date}'")
            print(f"Method: {metadata.get('extraction_method', 'unknown')}")
            print(f"Original fields: {metadata.get('original_fields', [])}")
            print(f"Promulgation_Date removed: {'Promulgation_Date' not in result}")
            
        except Exception as e:
            print(f"ERROR: {str(e)}")
    
    print("\n" + "=" * 60)
    print("Expected behavior:")
    print("1. When both Date and Promulgation_Date exist, Date should be preferred")
    print("2. When only one exists, use that one")
    print("3. When neither exists or both empty, Date should be empty string ''")
    print("4. Promulgation_Date field should always be removed from output")

if __name__ == "__main__":
    asyncio.run(test_merge_logic())
