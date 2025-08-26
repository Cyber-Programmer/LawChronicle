import glob
import pandas as pd
from pathlib import Path

folder = Path(r"d:\DigiFloat\LawChronicle\Missing Dates Excel")
files = sorted(folder.glob('*.xlsx'))

if not files:
    print('No xlsx files found in', folder)
    raise SystemExit(1)

for f in files:
    print('\nFILE:', f.name)
    try:
        x = pd.ExcelFile(f)
        print('  Sheets:', x.sheet_names)
        for sheet in x.sheet_names:
            try:
                df = pd.read_excel(f, sheet_name=sheet)
                cols = list(df.columns)
                print(f"    Sheet '{sheet}' columns ({len(cols)}): {cols[:20]}")
            except Exception as e:
                print(f"    Failed to read sheet '{sheet}': {e}")
    except Exception as e:
        print('  Failed to open file:', e)
