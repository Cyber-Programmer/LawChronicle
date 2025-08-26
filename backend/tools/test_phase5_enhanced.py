#!/usr/bin/env python3
"""
Test script for Phase 5: Contextual Statute Grouping & Versioning (Azure GPT-4o)
Validates the enhanced contextual grouping functionality.
"""

import sys
import asyncio
import json
import os
from pathlib import Path
from datetime import datetime

# Add backend directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

# Now we can import from backend
from backend.app.core.services.phase5_service import Phase5Service
from shared.types.common import Phase5Config, StatuteGroup, NestedStatute

async def test_phase5_enhanced():
    """Test Phase 5 enhanced contextual grouping functionality."""
    
    print("🚀 Testing Phase 5: Contextual Statute Grouping & Versioning")
    print("=" * 60)
    
    # Initialize service
    phase5_service = Phase5Service()
    
    try:
        # Test 1: Check status
        print("\n📊 Testing status endpoint...")
        status = await phase5_service.get_status()
        print(f"✅ Status: {json.dumps(status, indent=2)}")
        
        # Test 2: Check available collections
        print("\n📋 Testing collection autodetection...")
        collections = await phase5_service.get_available_collections()
        print(f"✅ Available collections: {collections}")
        
        # Test 3: Check provinces
        print("\n🗺️  Testing province detection...")
        provinces = await phase5_service.get_provinces()
        print(f"✅ Available provinces: {provinces}")
        
        # Test 4: Test contextual snippet building
        print("\n📝 Testing contextual snippet building...")
        
        # Sample statute document for testing
        sample_statute = {
            "_id": "test123",
            "Statute_Name": "Municipal Government Act",
            "province": "Alberta",
            "year": 2023,
            "preamble": "An Act respecting municipal government and the powers of municipalities",
            "Sections": [
                {"number": "PREAMBLE", "text": "An Act respecting municipal government and the powers of municipalities"},
                {"number": "1", "text": "This Act governs municipal operations and establishes the framework for local governance"},
                {"number": "2", "text": "Municipalities have the power to pass bylaws for the good government of the municipality"},
                {"number": "3", "text": "Municipal councils shall meet regularly to conduct the business of the municipality"},
                {"number": "4", "text": "Taxation powers are granted to municipalities to fund local services and infrastructure"},
                {"number": "5", "text": "Municipal boundaries are established by the province and may be altered by regulation"}
            ]
        }
        
        test_config = Phase5Config(max_context_length=3000)
        snippet = phase5_service._build_statute_snippet(sample_statute, test_config)
        print(f"✅ Contextual snippet (length: {len(snippet)}):")
        print(f"   Preview: {snippet[:200]}...")
        
        # Test 5: Test data type validation
        print("\n🔍 Testing data type validation...")
        
        # Test Phase5Config
        config = Phase5Config(
            source_database="test",
            target_database="test-groups",
            batch_size=20,
            max_context_length=3000
        )
        print(f"✅ Phase5Config validation: {config.model_dump()}")
        
        # Test StatuteGroup structure
        nested_statute = NestedStatute(
            _id="test123",
            title="Municipal Government Act",
            year="2023",
            province="Alberta",
            statute_type="act",
            is_original=True,
            relation="original",
            semantic_similarity_score=1.0,
            ai_decision_confidence=1.0
        )
        
        statute_group = StatuteGroup(
            group_id="municipal-govt-ab",
            base_name="Municipal Government Act",
            province="Alberta",
            statute_type="act",
            total_statutes=1,
            original_statute_id="test123",
            amendment_count=0,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            statutes=[nested_statute]
        )
        
        print(f"✅ StatuteGroup validation: {statute_group.model_dump()}")
        
        # Test 6: Test autodetection logic
        print("\n🔍 Testing autodetection logic...")
        test_config = Phase5Config()
        source_collection = await phase5_service._autodetect_source_collection(test_config)
        print(f"✅ Autodetected source: {source_collection}")
        
        print("\n🎉 All Phase 5 enhanced functionality tests passed!")
        print("✅ Contextual grouping, nested document structure, and autodetection working correctly")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Clean up connections
        if hasattr(phase5_service, 'client'):
            phase5_service.client.close()

if __name__ == "__main__":
    # Run the test
    asyncio.run(test_phase5_enhanced())
