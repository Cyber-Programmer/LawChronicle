import requests, json, sys

login_url = 'http://127.0.0.1:8000/api/v1/auth/login'
apply_url = 'http://127.0.0.1:8000/api/v1/phase4/search/apply-approved-dates'
file_path = r'D:\DigiFloat\LawChronicle\Missing Dates Excel\batch_1-search-results-20250820_for_upload.xlsx'

s = requests.Session()
try:
    resp = s.post(login_url, data={'username':'admin','password':'admin123'}, timeout=15)
except Exception as e:
    print('Login request failed:', e)
    sys.exit(2)
print('login status', resp.status_code)
try:
    print('login response:', resp.json())
except Exception:
    print('login response text:', resp.text[:1000])

if resp.status_code != 200:
    print('Login failed, aborting')
    sys.exit(1)

token = resp.json().get('data', {}).get('access_token')
if not token:
    print('No token returned, aborting')
    sys.exit(1)

headers = {'Authorization': f'Bearer {token}'}
print('uploading file:', file_path)
try:
    with open(file_path, 'rb') as fh:
        files = {'file': (file_path.split('\\')[-1], fh, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
        resp2 = s.post(apply_url, headers=headers, files=files, timeout=120)
except Exception as e:
    print('Upload failed:', e)
    sys.exit(2)

print('apply status', resp2.status_code)
try:
    print('apply response JSON:')
    print(json.dumps(resp2.json(), indent=2)[:4000])
except Exception:
    print('apply response text:', resp2.text[:4000])
    
if resp2.status_code != 200:
    sys.exit(1)
print('Done')
