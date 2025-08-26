#!/usr/bin/env python3
"""
Quick test to verify AI search with fixed field mapping
"""

import asyncio
import json
from datetime import datetime
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from backend.app.core.services.phase4_search_service import Phase4SearchService
from backend.app.core.database import DatabaseManager

async def test_ai_search_with_fixed_fields():
    """Test AI search with the corrected field mapping"""
    
    try:
        # Initialize services
        db_manager = DatabaseManager()
        await db_manager.connect()
        
        service = Phase4SearchService(db_manager)
        
        print("🔧 Testing AI Search with Fixed Field Mapping")
        print("=" * 60)
        
        # Test with single collection
        collection_names = ["5batch"]
        max_docs = 3  # Just test with a few documents
        
        print(f"📋 Testing with collection: {collection_names[0]}")
        print(f"📊 Max documents to test: {max_docs}")
        print()
        
        # Run AI search
        results = await service.search_dates_with_ai(
            collection_names=collection_names,
            max_docs=max_docs
        )
        
        print("🎯 Results Summary:")
        print(f"   - Total documents collected: {results.get('total_collected', 0)}")
        print(f"   - Total documents processed: {results.get('total_processed', 0)}")
        print(f"   - Total dates found: {results.get('total_dates_found', 0)}")
        print(f"   - Processing time: {results.get('processing_time', 0):.2f}s")
        print()
        
        # Show sample results if any
        if results.get('results') and len(results['results']) > 0:
            print("📄 Sample Results:")
            for i, doc in enumerate(results['results'][:2]):  # Show first 2
                print(f"\n   Document {i+1}:")
                print(f"     📋 Statute: {doc.get('Statute_Name', 'N/A')[:60]}...")
                print(f"     📅 Date Found: {doc.get('Extracted_Date', 'None')}")
                print(f"     🎯 Confidence: {doc.get('Confidence', 'N/A')}")
                print(f"     💭 Method: {doc.get('Method', 'N/A')}")
                if doc.get('Reasoning'):
                    print(f"     📝 Reasoning: {doc.get('Reasoning', '')[:100]}...")
        else:
            print("❌ No results found - this may indicate the documents still have no text")
            
        # Check if we actually have text content now
        if results.get('total_processed', 0) > 0:
            print("\n✅ SUCCESS: Documents are now being processed with text content!")
        else:
            print("\n❌ ISSUE: Documents are still not being processed - may need further investigation")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        await db_manager.disconnect()

if __name__ == "__main__":
    asyncio.run(test_ai_search_with_fixed_fields())
