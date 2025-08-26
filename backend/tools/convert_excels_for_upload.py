import pandas as pd
from pathlib import Path

folder = Path(r"d:\DigiFloat\LawChronicle\Missing Dates Excel")
out_folder = folder

mapping = {
    'Statute Name': 'Statute_Name',
    'Statute Name ': 'Statute_Name',
    'Document Id': 'Document_ID',
    'Document Id ': 'Document_ID',
    'Extracted Date': 'AI_Extracted_Date',
    'Confidence': 'Confidence_Score',
    'Current_Date': 'Current_Date'
}

files = sorted(folder.glob('*.xlsx'))
if not files:
    print('No files found in', folder)
    raise SystemExit(1)

for f in files:
    print('\nProcessing', f.name)
    x = pd.ExcelFile(f)
    # Prefer sheet Missing_Dates, else AI_Search_Results, else first
    sheet_name = None
    if 'Missing_Dates' in x.sheet_names:
        sheet_name = 'Missing_Dates'
    elif 'AI_Search_Results' in x.sheet_names:
        sheet_name = 'AI_Search_Results'
    else:
        sheet_name = x.sheet_names[0]
    print('  Using sheet:', sheet_name)
    df = pd.read_excel(f, sheet_name=sheet_name)
    # Normalize columns
    new_cols = {}
    for c in df.columns:
        cname = c.strip() if isinstance(c, str) else c
        if cname in mapping:
            new_cols[c] = mapping[cname]
        else:
            # canonicalize spaces and underscores
            nc = cname.replace(' ', '_')
            new_cols[c] = nc
    df.rename(columns=new_cols, inplace=True)

    # Ensure required columns exist
    required_cols = ['Statute_Name', 'Document_ID', 'AI_Extracted_Date', 'Confidence_Score']
    for col in required_cols:
        if col not in df.columns:
            df[col] = ''

    # Add Review_Status if missing; set Approved if AI_Extracted_Date non-empty
    if 'Review_Status' not in df.columns:
        df['Review_Status'] = df['AI_Extracted_Date'].apply(lambda v: 'Approved' if pd.notna(v) and str(v).strip()!='' else 'Pending')
    else:
        # Normalize values
        df['Review_Status'] = df['Review_Status'].astype(str).apply(lambda v: v if v.strip()!='' else 'Pending')

    # Save to new file
    out_name = f.stem + '_for_upload.xlsx'
    out_path = out_folder / out_name
    with pd.ExcelWriter(out_path, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Missing_Dates', index=False)
    print('  Saved converted file:', out_name)

print('\nConversion complete')
