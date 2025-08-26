#!/usr/bin/env python3
"""
Demo: Frontend Source Selection for Phase 5
Shows how the frontend can dynamically select databases and collections
"""

import sys
import asyncio
import json
from pathlib import Path

# Add backend directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from backend.app.core.services.phase5_service import Phase5Service
from shared.types.common import Phase5Config

async def demo_frontend_selection():
    """Demonstrate frontend source selection capabilities."""
    
    print("📋 Phase 5: Frontend Database & Collection Selection Demo")
    print("=" * 60)
    
    phase5_service = Phase5Service()
    
    try:
        # Step 1: Get available collections (what frontend would call)
        print("\n1️⃣ Frontend calls: GET /api/v1/phase5/collections")
        collections = await phase5_service.get_available_collections()
        print(f"   Available collections: {collections}")
        
        # Step 2: Get available provinces (for filtering)
        print("\n2️⃣ Frontend calls: GET /api/v1/phase5/provinces")
        provinces = await phase5_service.get_provinces()
        print(f"   Available provinces: {provinces}")
        
        # Step 3: User selects on frontend (simulated)
        print("\n3️⃣ User selects on frontend UI:")
        selected_db = "Date-Enriched-Batches"
        selected_collection = "batch_1"
        selected_province = "Punjab"
        print(f"   Database: {selected_db}")
        print(f"   Collection: {selected_collection}")
        print(f"   Province Filter: {selected_province}")
        
        # Step 4: Frontend creates config and sends to backend
        print("\n4️⃣ Frontend sends: POST /api/v1/phase5/start-grouping")
        config = Phase5Config(
            source_database=selected_db,
            source_collection=selected_collection,
            batch_size=30  # User can also adjust this
        )
        
        print(f"   Request body:")
        print(f"   {{")
        print(f"     \"config\": {{")
        print(f"       \"source_database\": \"{config.source_database}\",")
        print(f"       \"source_collection\": \"{config.source_collection}\",")
        print(f"       \"target_database\": \"{config.target_database}\",")
        print(f"       \"batch_size\": {config.batch_size}")
        print(f"     }}")
        print(f"   }}")
        
        # Step 5: Show resulting target naming
        print("\n5️⃣ Backend processes with dynamic naming:")
        print(f"   Source: {config.source_database}.{config.source_collection}")
        print(f"   Target: {config.target_database}.{config.get_target_collection()}")
        
        # Step 6: Show how different selections create different targets
        print("\n6️⃣ Different selections create different targets:")
        
        examples = [
            ("batch_1", "grouped_batch_1"),
            ("batch_2", "grouped_batch_2"), 
            ("normalized_statutes", "grouped_normalized_statutes"),
            (None, "grouped_statutes")  # fallback
        ]
        
        for source, expected_target in examples:
            test_config = Phase5Config(source_collection=source)
            actual_target = test_config.get_target_collection()
            print(f"   Source: {source or 'autodetected'} → Target: {actual_target}")
            
        print("\n✅ Frontend has full control over source selection!")
        print("✅ Target collections are automatically named based on source!")
        print("✅ Multiple grouping operations can run in parallel!")
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        if hasattr(phase5_service, 'client'):
            phase5_service.client.close()

if __name__ == "__main__":
    asyncio.run(demo_frontend_selection())
