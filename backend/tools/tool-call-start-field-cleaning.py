import requests
url = 'http://localhost:8000/api/v1/phase3/start-field-cleaning'
payload = {
    "source_database": "Statutes",
    "source_collection": "normalized_statutes",
    "target_database": "Batched-Statutes",
    "target_collection_prefix": "batch",
    "batch_size": 10,
    "enable_ai_cleaning": False
}
resp = requests.post(url, json=payload, timeout=30)
print('Status:', resp.status_code)
try:
    print(resp.json())
except Exception:
    print(resp.text)
