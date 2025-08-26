import requests

# Test: No filter (all statutes)
resp_all = requests.post(
    'http://localhost:8000/api/v1/phase2/preview-normalized-structure?limit=25&skip=0',
    json={}
)
print('All statutes:', resp_all.json().get('filtered_count'), 'sections:', resp_all.json().get('total_sections'))

# Test: Has preamble filter
resp_preamble = requests.post(
    'http://localhost:8000/api/v1/phase2/preview-normalized-structure?limit=25&skip=0',
    json={"filter_preamble": True}
)
print('Has preamble:', resp_preamble.json().get('filtered_count'), 'sections:', resp_preamble.json().get('total_sections'))

# Test: Numeric section filter
resp_numeric = requests.post(
    'http://localhost:8000/api/v1/phase2/preview-normalized-structure?limit=25&skip=0',
    json={"filter_numeric": True}
)
print('Has numeric section:', resp_numeric.json().get('filtered_count'), 'sections:', resp_numeric.json().get('total_sections'))
