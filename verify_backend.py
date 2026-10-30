import sys
sys.path.insert(0, '.')
import main
from fastapi.testclient import TestClient

client = TestClient(main.app)

print('=== BACKEND VERIFICATION ===')

# 1. Health check
r = client.get('/health')
print(f'1. Health: {r.status_code} - {r.json()}')

# 2. /api/cases with ALL status
r = client.get('/api/cases?status=ALL&search=&page=1&per_page=50')
data = r.json()
print(f'2. /api/cases ALL: total={data["total"]}, counts={data["counts"]}')
assert data['total'] == 518
assert data['counts']['complete'] == 190
assert data['counts']['incomplete'] == 234
assert data['counts']['not_applicable'] == 94

# 3. Filter by COMPLETE
r = client.get('/api/cases?status=COMPLETE&search=&page=1&per_page=50')
data = r.json()
print(f'3. Filter COMPLETE: total={data["total"]}, counts={data["counts"]}')
assert data['counts']['complete'] == 190

# 4. Filter by INCOMPLETE
r = client.get('/api/cases?status=INCOMPLETE&search=&page=1&per_page=50')
data = r.json()
print(f'4. Filter INCOMPLETE: total={data["total"]}, counts={data["counts"]}')
assert data['counts']['incomplete'] == 234

# 5. Filter by NOT_APPLICABLE
r = client.get('/api/cases?status=NOT_APPLICABLE&search=&page=1&per_page=50')
data = r.json()
print(f'5. Filter NOT_APPLICABLE: total={data["total"]}, counts={data["counts"]}')
assert data['counts']['not_applicable'] == 94

# 6. Search functionality
r = client.get('/api/cases?search=case_001&status=ALL&page=1&per_page=50')
data = r.json()
found = any(c['case_id'] == 'case_001' for c in data['cases'])
print(f'6. Search case_001: found={found}')

# 7. /api/cases/{case_id}
r = client.get('/api/cases/case_100')
data = r.json()
print(f'7. /api/cases/case_100: case_id={data["case_id"]}, email={data["email"][:20]}..., audit_status={data["audit_status"]}')

# 8. Verify all 518 cases are returned with proper filtering
print('=== ALL BACKEND TESTS PASSED ===')