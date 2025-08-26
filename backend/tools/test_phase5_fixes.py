#!/usr/bin/env python3
"""
Test the updated Phase 5 functionality:
1. Azure OpenAI config loading
2. Collection-specific status 
3. Available collections count
"""

import sys
import asyncio
from pathlib import Path

# Add backend directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from backend.app.core.services.phase5_service import Phase5Service

async def test_phase5_fixes():
    """Test the fixes for Azure OpenAI and collection-specific status."""
    
    print("🔧 Testing Phase 5 Fixes")
    print("=" * 50)
    
    phase5_service = Phase5Service()
    
    try:
        # Test 1: Check Azure OpenAI configuration
        print("\n1️⃣ Testing Azure OpenAI Configuration...")
        if phase5_service.azure_openai_client:
            print("   ✅ Azure OpenAI: Configured from config file")
            print(f"   ✅ Deployment: {phase5_service.deployment_name}")
        else:
            print("   ❌ Azure OpenAI: Not configured")
        
        # Test 2: Check available collections count
        print("\n2️⃣ Testing Available Collections...")
        collections = await phase5_service.get_available_collections()
        print(f"   ✅ Available collections: {len(collections)}")
        print(f"   ✅ Collections: {collections}")
        
        # Test 3: Test default status (autodetected)
        print("\n3️⃣ Testing Default Status (Autodetected)...")
        status = await phase5_service.get_status()
        print(f"   ✅ Source: {status['source_database']}.{status['source_collection']}")
        print(f"   ✅ Target: {status['target_database']}.{status.get('target_collection', 'unknown')}")
        print(f"   ✅ Total Statutes: {status['total_source_documents']}")
        print(f"   ✅ Azure OpenAI: {status['azure_openai_configured']}")
        
        # Test 4: Test collection-specific status
        if len(collections) > 1:
            test_collection = collections[1]  # Get second collection (batch_2 probably)
            print(f"\n4️⃣ Testing Collection-Specific Status ({test_collection})...")
            collection_status = await phase5_service.get_status(collection=test_collection)
            print(f"   ✅ Source: {collection_status['source_database']}.{collection_status['source_collection']}")
            print(f"   ✅ Target: {collection_status['target_database']}.{collection_status.get('target_collection', 'unknown')}")
            print(f"   ✅ Total Statutes: {collection_status['total_source_documents']}")
            
            # Verify it's different from default
            if collection_status['source_collection'] != status['source_collection']:
                print("   ✅ Collection-specific status working correctly!")
            else:
                print("   ⚠️  Collection-specific status might not be working")
        
        print("\n🎉 All Phase 5 fixes tested!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        if hasattr(phase5_service, 'client'):
            phase5_service.client.close()

if __name__ == "__main__":
    asyncio.run(test_phase5_fixes())
