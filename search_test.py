import sys
sys.path.insert(0, '.')
import main
from fastapi.testclient import TestClient

client = TestClient(main.app)

r = client.get('/api/cases?status=ALL&search=&page=1&per_page=50')
data = r.json()
case_ids = [c['case_id'] for c in data['cases']]
print(f'Total cases: {len(case_ids)}')
print(f'case_001 in list: {"case_001" in case_ids}')
print(f'First 5 case_ids: {case_ids[:5]}')
print(f'case_100 in list: {"case_100" in case_ids}')

r = client.get('/api/cases?search=case_001&status=ALL&page=1&per_page=50')
data = r.json()
print(f'Search case_001 results: {len(data["cases"])} cases')
print(f'Cases: {data["cases"]}')