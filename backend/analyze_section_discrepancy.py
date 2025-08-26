"""
Diagnostic script to analyze section count discrepancy between raw and normalized collections
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.database import connect_to_mongo
from app.core.config import settings

async def analyze_section_counts():
    """
    Analyze section counts to understand the discrepancy between raw (100k+) and normalized (25k) sections
    """
    try:
        print("🔍 Starting section count analysis...")
        
        database = await connect_to_mongo()
        
        # Check both collections
        raw_collection = database["raw_statutes"]
        normalized_collection = database["normalized_statutes"]
        
        print(f"\n📊 Collection Overview:")
        raw_count = await raw_collection.count_documents({})
        normalized_count = await normalized_collection.count_documents({})
        
        print(f"   Raw Collection: {raw_count:,} documents")
        print(f"   Normalized Collection: {normalized_count:,} documents")
        
        # Analyze raw collection structure
        print(f"\n🔍 Raw Collection Analysis:")
        raw_sample = await raw_collection.find({}).limit(5).to_list(length=5)
        
        if raw_sample:
            first_raw = raw_sample[0]
            print(f"   Sample document fields: {list(first_raw.keys())}")
            print(f"   Sample Statute_Name: {first_raw.get('Statute_Name', 'Not found')}")
            print(f"   Sample Section: {first_raw.get('Section', 'Not found')}")
            print(f"   Has Sections array: {'Sections' in first_raw}")
            
            if 'Sections' in first_raw:
                print(f"   Sections array length: {len(first_raw.get('Sections', []))}")
            
            # Check if each raw document represents a single section
            section_indicators = []
            for key in ['Section', 'section', 'number', 'definition', 'content']:
                if key in first_raw:
                    section_indicators.append(key)
            
            print(f"   Section indicator fields: {section_indicators}")
            print(f"   → Raw documents appear to be: {'Individual sections' if section_indicators else 'Unknown structure'}")
        
        # Analyze normalized collection structure
        print(f"\n🔍 Normalized Collection Analysis:")
        normalized_sample = await normalized_collection.find({}).limit(3).to_list(length=3)
        
        if normalized_sample:
            first_normalized = normalized_sample[0]
            print(f"   Sample document fields: {list(first_normalized.keys())}")
            print(f"   Sample Statute_Name: {first_normalized.get('Statute_Name', 'Not found')}")
            sections = first_normalized.get('Sections', [])
            print(f"   Sections array length: {len(sections)}")
            
            if sections:
                print(f"   Sample section structure: {list(sections[0].keys()) if sections else 'No sections'}")
        
        # Calculate section counts using aggregation
        print(f"\n📈 Section Count Calculations:")
        
        # Raw collection: if each document is a section
        raw_as_sections = raw_count
        print(f"   Raw (if each doc = 1 section): {raw_as_sections:,}")
        
        # Raw collection: if documents have Sections arrays
        raw_sections_pipeline = [
            {"$project": {"section_count": {"$size": {"$ifNull": ["$Sections", []]}}}},
            {"$group": {"_id": None, "total_sections": {"$sum": "$section_count"}}}
        ]
        raw_sections_result = await raw_collection.aggregate(raw_sections_pipeline).to_list(length=1)
        raw_from_arrays = raw_sections_result[0]["total_sections"] if raw_sections_result else 0
        print(f"   Raw (from Sections arrays): {raw_from_arrays:,}")
        
        # Normalized collection: sections in arrays
        normalized_sections_pipeline = [
            {"$project": {"section_count": {"$size": {"$ifNull": ["$Sections", []]}}}},
            {"$group": {"_id": None, "total_sections": {"$sum": "$section_count"}}}
        ]
        normalized_sections_result = await normalized_collection.aggregate(normalized_sections_pipeline).to_list(length=1)
        normalized_total = normalized_sections_result[0]["total_sections"] if normalized_sections_result else 0
        print(f"   Normalized (grouped sections): {normalized_total:,}")
        
        # Analysis
        print(f"\n🧮 Analysis:")
        if raw_as_sections > 100000:
            print(f"   ✅ Raw collection has {raw_as_sections:,} documents (matches your 100k+ observation)")
        
        if normalized_total > 0:
            ratio = raw_as_sections / normalized_total if normalized_total > 0 else 0
            print(f"   📉 Section reduction ratio: {ratio:.1f}x (from {raw_as_sections:,} to {normalized_total:,})")
            
            avg_sections_per_statute = normalized_total / normalized_count if normalized_count > 0 else 0
            print(f"   📊 Average sections per statute: {avg_sections_per_statute:.1f}")
            
            if ratio > 3:
                print(f"   ⚠️  HIGH REDUCTION DETECTED:")
                print(f"      - Possible causes:")
                print(f"        1. Duplicate sections in raw data were merged")
                print(f"        2. Some raw documents were filtered out during normalization")
                print(f"        3. Data structure transformation lost some sections")
                print(f"        4. Sections were deduplicated by content")
        
        # Check for potential issues
        print(f"\n🔎 Potential Issues to Investigate:")
        
        # Check for duplicate statute names in raw
        duplicate_statute_pipeline = [
            {"$group": {"_id": "$Statute_Name", "count": {"$sum": 1}}},
            {"$match": {"count": {"$gt": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 5}
        ]
        raw_duplicates = await raw_collection.aggregate(duplicate_statute_pipeline).to_list(length=5)
        
        if raw_duplicates:
            print(f"   📋 Top duplicate statute names in raw collection:")
            for dup in raw_duplicates:
                print(f"      - '{dup['_id']}': {dup['count']} documents")
            
            total_duplicates = sum(dup['count'] - 1 for dup in raw_duplicates)  # -1 because one copy is not a duplicate
            print(f"   💡 This could explain some reduction: {total_duplicates:,} duplicate documents found in sample")
        
        # Check normalization metadata if available
        metadata_collection = database["normalization_metadata"]
        metadata = await metadata_collection.find({}).limit(1).to_list(length=1)
        if metadata:
            print(f"   📝 Normalization metadata found:")
            meta = metadata[0]
            if 'total_documents_processed' in meta:
                print(f"      - Documents processed: {meta['total_documents_processed']:,}")
            if 'unique_statutes' in meta:
                print(f"      - Unique statutes created: {meta['unique_statutes']:,}")
            if 'duplicate_sections_removed' in meta:
                print(f"      - Duplicate sections removed: {meta.get('duplicate_sections_removed', 'Not tracked'):,}")
        
        return {
            "raw_documents": raw_count,
            "normalized_documents": normalized_count, 
            "raw_sections_estimate": raw_as_sections,
            "normalized_sections": normalized_total,
            "reduction_ratio": raw_as_sections / normalized_total if normalized_total > 0 else 0
        }
        
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    print("🔍 SECTION COUNT DISCREPANCY ANALYSIS")
    print("=" * 50)
    
    result = asyncio.run(analyze_section_counts())
    
    if result:
        print(f"\n📋 SUMMARY:")
        print(f"   Raw → Normalized: {result['raw_sections_estimate']:,} → {result['normalized_sections']:,}")
        print(f"   Reduction Factor: {result['reduction_ratio']:.1f}x")
        
        if result['reduction_ratio'] > 3:
            print(f"\n⚠️  INVESTIGATION NEEDED:")
            print(f"   The {result['reduction_ratio']:.1f}x reduction is significant.")
            print(f"   Most likely causes:")
            print(f"   1. Raw data contains many duplicate sections that were merged")
            print(f"   2. Normalization process filters out invalid/incomplete sections")
            print(f"   3. Multiple raw documents represent the same logical section")
    else:
        print("❌ Analysis failed - check database connection and collection names")
