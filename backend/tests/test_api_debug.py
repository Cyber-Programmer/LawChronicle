import requests
import json

# Test the scan endpoint
try:
    print("Testing scan endpoint...")
    response = requests.post('http://localhost:8000/api/v1/phase4/search/scan-missing-dates', 
                           json={'collections': ['batch_1']})
    print(f"Response status: {response.status_code}")
    print(f"Response data: {response.json()}")
    
    if response.status_code == 200:
        scan_id = response.json()['scan_id']
        print(f"Scan started with ID: {scan_id}")
        
        # Test SSE connection
        print("Testing SSE connection...")
        import sseclient
        import time
        
        sse_url = f'http://localhost:8000/api/v1/phase4/search/progress-stream/{scan_id}'
        response = requests.get(sse_url, stream=True)
        client = sseclient.SSEClient(response)
        
        for event in client.events():
            print(f"SSE Event: {event.data}")
            time.sleep(1)
            break  # Just test one event
        
except Exception as e:
    print(f"Error: {e}")
