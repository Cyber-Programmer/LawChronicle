#!/usr/bin/env python3
"""Quick test of Phase 5 API"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "backend"))
from backend.app.core.services.phase5_service import Phase5Service

async def test_api():
    service = Phase5Service()
    
    print("=== Testing Phase 5 API ===")
    
    # Test collections
    collections = await service.get_available_collections()
    print(f"Collections: {len(collections)}")
    
    # Test status without collection
    status1 = await service.get_status()
    print(f"Default: {status1['source_collection']} = {status1['total_source_documents']} statutes")
    
    # Test status with batch_2
    status2 = await service.get_status(collection="batch_2")
    print(f"batch_2: {status2['source_collection']} = {status2['total_source_documents']} statutes")
    
    # Test status with batch_3  
    status3 = await service.get_status(collection="batch_3")
    print(f"batch_3: {status3['source_collection']} = {status3['total_source_documents']} statutes")
    
    service.client.close()

if __name__ == "__main__":
    asyncio.run(test_api())
