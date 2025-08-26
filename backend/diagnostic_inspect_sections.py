import asyncio
from app.core.database import connect_to_mongo

async def inspect_sections():
    db = await connect_to_mongo()
    normalized_col = db["normalized_statutes"]
    sample_docs = await normalized_col.find({}).limit(10).to_list(length=10)
    for i, doc in enumerate(sample_docs):
        statute_name = doc.get("Statute_Name", "Unknown")
        sections = doc.get("Sections", [])
        print(f"{i+1}. {statute_name} - Sections: {len(sections)}")
        for j, section in enumerate(sections[:3]):
            print(f"   Section {j+1}: {section}")
        print()

if __name__ == "__main__":
    asyncio.run(inspect_sections())
