"""
Diagnostic script to count statutes and sections with a preamble
"""
import asyncio
from app.core.database import connect_to_mongo

async def count_preamble_statutes():
    db = await connect_to_mongo()
    normalized_col = db["normalized_statutes"]

    # Statutes with at least one section labeled 'preamble'
    pipeline = [
        {"$match": {"Sections.number": {"$regex": "^preamble$", "$options": "i"}}},
        {"$count": "statutes_with_preamble"}
    ]
    statutes_result = await normalized_col.aggregate(pipeline).to_list(length=1)
    statutes_with_preamble = statutes_result[0]["statutes_with_preamble"] if statutes_result else 0

    # Total sections labeled 'preamble'
    pipeline_sections = [
        {"$unwind": "$Sections"},
        {"$match": {"Sections.number": {"$regex": "^preamble$", "$options": "i"}}},
        {"$count": "sections_with_preamble"}
    ]
    sections_result = await normalized_col.aggregate(pipeline_sections).to_list(length=1)
    sections_with_preamble = sections_result[0]["sections_with_preamble"] if sections_result else 0

    # Total statutes
    total_statutes = await normalized_col.count_documents({})
    # Total sections
    pipeline_total_sections = [
        {"$project": {"section_count": {"$size": {"$ifNull": ["$Sections", []]}}}},
        {"$group": {"_id": None, "total_sections": {"$sum": "$section_count"}}}
    ]
    total_sections_result = await normalized_col.aggregate(pipeline_total_sections).to_list(length=1)
    total_sections = total_sections_result[0]["total_sections"] if total_sections_result else 0

    print(f"Statutes with preamble: {statutes_with_preamble} / {total_statutes}")
    print(f"Sections labeled preamble: {sections_with_preamble} / {total_sections}")
    print(f"Percent statutes with preamble: {(statutes_with_preamble/total_statutes)*100:.2f}%")
    print(f"Percent sections labeled preamble: {(sections_with_preamble/total_sections)*100:.2f}%")

if __name__ == "__main__":
    asyncio.run(count_preamble_statutes())
