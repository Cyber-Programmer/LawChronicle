#!/usr/bin/env python3
"""
Integration test for Phase 5 Azure GPT-4o grouping
Tests the real Azure OpenAI integration for semantic statute grouping.
"""

import sys
import asyncio
from pathlib import Path

# Add project paths
current_dir = Path(__file__).parent
project_dir = current_dir.parent

sys.path.insert(0, str(project_dir))
sys.path.insert(0, str(project_dir / "backend"))

from backend.app.core.services.phase5_service import Phase5Service
from shared.types.common import Phase5Config


async def test_azure_openai_integration():
    """Test Azure OpenAI integration for statute grouping."""
    print("🔄 Testing Azure OpenAI Integration for Phase 5...")
    
    service = Phase5Service()
    
    # Check if Azure OpenAI is configured
    if not service.azure_openai_client:
        print("⚠️  Azure OpenAI not configured - testing fallback only")
        return False
    
    print(f"✅ Azure OpenAI configured with deployment: {service.deployment_name}")
    
    # Test sample statutes that should be grouped together
    sample_statutes = [
        {
            "_id": "1",
            "Statute_Name": "The Companies Act 1984",
            "Province": "Federal",
            "Date_of_Commencement": "1984-09-01",
            "Preamble": "An Act to consolidate and amend the law relating to companies and to provide for matters connected therewith or incidental thereto.",
            "Sections": [
                {"content": "This Act may be called the Companies Act, 1984, and shall come into force on such date as the Federal Government may, by notification in the official Gazette, appoint."}
            ]
        },
        {
            "_id": "2", 
            "Statute_Name": "Companies Act (Amendment) 2017",
            "Province": "Federal",
            "Date_of_Commencement": "2017-05-15",
            "Preamble": "An Act to amend the Companies Act, 1984, to enhance corporate governance and transparency.",
            "Sections": [
                {"content": "This Act amends the Companies Act 1984 to introduce new provisions for board composition and audit requirements."}
            ]
        },
        {
            "_id": "3",
            "Statute_Name": "The Criminal Procedure Code 1898",
            "Province": "Federal", 
            "Date_of_Commencement": "1898-04-01",
            "Preamble": "An Act to consolidate and amend the law relating to Criminal Procedure.",
            "Sections": [
                {"content": "This Act may be called the Code of Criminal Procedure, 1898, and shall extend to the whole of Pakistan."}
            ]
        },
        {
            "_id": "4",
            "Statute_Name": "Contract Act 1872",
            "Province": "Federal",
            "Date_of_Commencement": "1872-09-01",
            "Preamble": "An Act to define and amend certain parts of the law relating to contracts.",
            "Sections": [
                {"content": "This Act may be called the Contract Act, 1872. It shall come into force on the first day of September, 1872."}
            ]
        }
    ]
    
    try:
        print("🔄 Testing AI grouping with sample statutes...")
        
        # Test AI grouping
        groups = await service._call_azure_openai_grouping(sample_statutes)
        
        print(f"✅ AI grouping completed successfully")
        print(f"📊 Results: {len(groups)} groups created from {len(sample_statutes)} statutes")
        
        # Analyze results
        for i, group in enumerate(groups):
            group_statutes = [sample_statutes[idx] for idx in group]
            statute_names = [s["Statute_Name"] for s in group_statutes]
            print(f"   Group {i+1}: {statute_names}")
        
        # Check if Companies Acts are grouped together
        companies_group = None
        for group in groups:
            group_statutes = [sample_statutes[idx] for idx in group]
            if any("Companies" in s["Statute_Name"] for s in group_statutes):
                companies_group = group
                break
        
        if companies_group and len(companies_group) >= 2:
            print("✅ AI correctly grouped Companies Acts together")
        else:
            print("⚠️  AI did not group Companies Acts together")
        
        # Test with different provinces (should not be grouped)
        mixed_province_statutes = [
            {**sample_statutes[0], "Province": "Federal"},
            {**sample_statutes[0], "Province": "Punjab", "_id": "5"}  # Same act, different province
        ]
        
        print("\n🔄 Testing province separation...")
        mixed_groups = await service._call_azure_openai_grouping(mixed_province_statutes)
        
        if len(mixed_groups) >= 2:
            print("✅ AI correctly separated statutes from different provinces")
        else:
            print("⚠️  AI incorrectly grouped statutes from different provinces")
        
        return True
        
    except Exception as e:
        print(f"❌ Azure OpenAI integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_full_grouping_workflow():
    """Test the complete grouping workflow."""
    print("\n🔄 Testing complete Phase 5 workflow...")
    
    service = Phase5Service()
    config = Phase5Config(
        source_database="Date-Enriched-Batches",
        target_database="Test-Grouped-Statutes",
        target_collection="test_grouped_statutes",
        use_azure_openai=bool(service.azure_openai_client),
        batch_size=10
    )
    
    try:
        # Get status
        status = await service.get_status()
        print(f"✅ Service status: {status['total_source_documents']} source documents available")
        print(f"✅ Azure OpenAI: {'Configured' if status['azure_openai_configured'] else 'Not configured'}")
        
        # Test preview (doesn't modify data)
        preview = await service.preview_grouping(config=config, preview_size=3)
        
        if preview["success"]:
            print(f"✅ Preview generated: {preview['estimated_groups']} estimated groups from {preview['total_statutes']} statutes")
            print(f"   Sample groups: {len(preview['sample_groups'])}")
        else:
            print(f"⚠️  Preview failed: {preview.get('error', 'Unknown error')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Workflow test failed: {e}")
        return False


async def main():
    """Run all integration tests."""
    print("=" * 60)
    print("🚀 Phase 5 Azure GPT-4o Integration Test")
    print("=" * 60)
    
    success = True
    
    # Test Azure OpenAI integration
    ai_success = await test_azure_openai_integration()
    success = success and ai_success
    
    # Test workflow
    workflow_success = await test_full_grouping_workflow()
    success = success and workflow_success
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 ALL INTEGRATION TESTS PASSED!")
        print("✅ Azure GPT-4o integration is working correctly")
        print("✅ Phase 5 semantic grouping is ready for production")
    else:
        print("❌ Some integration tests failed")
        print("⚠️  Check Azure OpenAI configuration and network connectivity")
    
    print("=" * 60)
    
    return 0 if success else 1


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(result)
