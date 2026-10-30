import sys
sys.path.insert(0, '.')

with open('C:\\Users\\usamah\\Desktop\\Hackerrank_hackathon\\main.py') as f:
    content = f.read()

# Check for key elements
checks = [
    ('csv.field_size_limit', 'csv.field_size_limit' in content),
    ('_get_deletion_requests', '_get_deletion_requests' in content),
    ('load_output_data', 'def load_output_data' in content),
    ('possible_output_paths', 'possible_output_paths' in content),
    ('possible_requests_paths', 'possible_requests_paths' in content),
    ('/api/cases returns dict', 'total' in content and 'counts' in content),
    ('audit_status in load_output', 'audit_status' in content),
]

for name, result in checks:
    print(f'{name}: {"PASS" if result else "FAIL"}')