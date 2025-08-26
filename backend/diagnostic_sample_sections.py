"""
Sample diagnostic: Print first section of first 10 statutes to inspect preamble labeling
"""
import asyncio
from app.core.database import connect_to_mongo

async def sample_preamble_sections():
    db = await connect_to_mongo()
    normalized_col = db["normalized_statutes"]
    sample_docs = await normalized_col.find({}).limit(10).to_list(length=10)
    for i, doc in enumerate(sample_docs):
        statute_name = doc.get("Statute_Name", "Unknown")
        sections = doc.get("Sections", [])
        if sections:
            first_section = sections[0]
            print(f"{i+1}. {statute_name}")
            print(f"   First section: {first_section}")
        else:
            print(f"{i+1}. {statute_name} (no sections)")

if __name__ == "__main__":
    asyncio.run(sample_preamble_sections())
