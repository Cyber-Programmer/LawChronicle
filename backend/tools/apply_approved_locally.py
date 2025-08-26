import asyncio
from pathlib import Path
import pandas as pd
from app.api.v1.endpoints.phase4_search import apply_approved_dates
from app.core.services.phase4_search_service import Phase4SearchService

async def main(file_path):
    svc = Phase4SearchService()
    # Read file like the endpoint
    content = Path(file_path).read_bytes()
    try:
        df = pd.read_excel(content, sheet_name='Missing_Dates')
    except Exception:
        x = pd.ExcelFile(content)
        df = pd.read_excel(content, sheet_name=x.sheet_names[0])
    df.columns = [c.strip().replace(' ', '_') if isinstance(c, str) else c for c in df.columns]
    approved_mask = df['Review_Status'].astype(str).str.lower() == 'approved'
    approved = df[approved_mask].to_dict('records')
    print('Approved rows count:', len(approved))
    # Use simplified logic to print which updates would be performed
    for r in approved[:5]:
        print(r)

if __name__ == '__main__':
    import sys
    p = sys.argv[1] if len(sys.argv)>1 else r'd:\DigiFloat\LawChronicle\Missing Dates Excel\batch_1-search-results-20250820_for_upload.xlsx'
    asyncio.run(main(p))
