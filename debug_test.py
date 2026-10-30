import sys
sys.path.insert(0, '.')
import main
from fastapi.testclient import TestClient

client = TestClient(main.app)
response = client.get('/api/cases?status=ALL&search=&page=1&per_page=50')
data = response.json()
counts = data.get('counts', {})
print(f'Total: {data.get("total")}')
print(f'Counts: {counts}')
print(f'First 5 cases audit_status:')
for c in data.get('cases', [])[:5]:
    print(f'  {c["case_id"]}: audit_status={c["audit_status"]}, deletion_status={c["deletion_status"]}')

# Now test filtered
print('\n--- Filtered NOT_APPLICABLE ---')
response2 = client.get('/api/cases?status=NOT_APPLICABLE&search=&page=1&per_page=50')
data2 = response2.json()
counts2 = data2.get('counts', {})
print(f'Filtered total: {data2.get("total")}')
print(f'Filtered counts: {counts2}')

print('\n--- First 3 filtered cases ---')
for c in data2.get('cases', [])[:3]:
    print(f'  {c["case_id"]}: audit_status={c["audit_status"]}, deletion_status={c["deletion_status"]}')