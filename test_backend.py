import sys
sys.path.insert(0, '.')
import main
from fastapi.testclient import TestClient

client = TestClient(main.app)

# Test health endpoint
print("Testing /health endpoint...")
response = client.get("/health")
print(f"  Status: {response.status_code}")
assert response.status_code == 200
print(f"  Body: {response.json()}")

# Test /api/cases endpoint
print("\nTesting /api/cases endpoint (ALL)...")
response = client.get("/api/cases?status=ALL&search=&page=1&per_page=50")
data = response.json()
print(f"  Status: {response.status_code}")
assert response.status_code == 200
print(f"  total: {data.get('total')}")
print(f"  counts: {data.get('counts')}")
assert data["total"] == 518, f"Expected total=518, got {data['total']}"
assert data["counts"]["complete"] > 0, "Expected complete > 0"
assert data["counts"]["not_applicable"] == 94, f"Expected not_applicable=94, got {data['counts']['not_applicable']}"
print("  Assertions passed!")

# Print first 3 cases
print(f"  First 3 cases:")
for c in data.get('cases', [])[:3]:
    print(f'    {c["case_id"]}: audit_status={c["audit_status"]}, email={c["email"][:20] if c["email"] else "N/A"}...')

# Test /api/cases/{case_id} endpoint
print("\nTesting /api/cases/case_100 endpoint...")
response = client.get("/api/cases/case_100")
print(f"  Status: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"  case_id: {data.get('case_id')}")
    print(f"  email: {data.get('email')}")
    print(f"  deletion_status: {data.get('deletion_status')}")
    print(f"  audit_status: {data.get('audit_status')}")
    print(f"  steps count: {len(data.get('steps', []))}")
    print(f"  audit_at: {data.get('audit_at')}")
    print(f"  historical_emails: {data.get('historical_emails')}")
    print(f"  account_resources: {data.get('account_resources')}")
    assert data["case_id"] == "case_100", f"Expected case_100, got {data['case_id']}"
    print("  Assertions passed!")
else:
    print(f"  Error: {response.text}")

# Test filtered endpoints
print("\n--- Testing FILTER BY COMPLETE ---")
response = client.get("/api/cases?status=COMPLETE&search=&page=1&per_page=50")
data = response.json()
print(f"  total: {data.get('total')}")
print(f"  counts: {data.get('counts')}")
assert data["counts"]["complete"] > 0, "Expected complete > 0 in filter"

print("\n--- Testing FILTER BY INCOMPLETE ---")
response = client.get("/api/cases?status=INCOMPLETE&search=&page=1&per_page=50")
data = response.json()
print(f"  total: {data.get('total')}")
print(f"  counts: {data.get('counts')}")
assert data["counts"]["incomplete"] > 0, "Expected incomplete > 0 in filter"

print("\n--- Testing FILTER BY NOT_APPLICABLE ---")
response = client.get("/api/cases?status=NOT_APPLICABLE&search=&page=1&per_page=50")
data = response.json()
print(f"  total: {data.get('total')}")
print(f"  counts: {data.get('counts')}")
assert data["counts"]["not_applicable"] > 0, "Expected not_applicable > 0 in filter"

print("\n--- Testing SEARCH ---")
response = client.get("/api/cases?search=case_100&status=ALL&page=1&per_page=50")
data = response.json()
print(f"  total: {data.get('total')}")
print(f"  cases count: {len(data.get('cases', []))}")
# Should find case_100
found = any(c["case_id"] == "case_100" for c in data.get("cases", []))
print(f"  case_100 found: {found}")

print("\n\nAll tests passed!")