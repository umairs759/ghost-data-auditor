import csv
import json
import sys

# Increase CSV field size limit
try:
    csv.field_size_limit(500 * 1024 * 1024)  # 500MB
except OverflowError:
    csv.field_size_limit(sys.maxsize // 10)

with open('output.csv') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

print('Total rows:', len(rows))
print('Line count:', len(rows) + 1)  # +1 for header

# Count statuses
statuses = {}
for r in rows:
    s = r['deletion_status']
    statuses[s] = statuses.get(s, 0) + 1
print('Status counts:', statuses)

# Count empty steps_json: []
empty_count = sum(1 for r in rows if r['steps_json'].strip() == '[]')
non_empty_count = sum(1 for r in rows if r['steps_json'].strip() != '[]')
print('Empty steps_json: [] count:', empty_count)
print('Non-empty steps_json count:', non_empty_count)

# Check DELETATION
deletation_count = sum(1 for r in rows if 'DELETATION' in r['steps_json'])
print('DELETATION count:', deletation_count)

# Print first 5 rows with steps_json lengths
print('\nFirst 5 rows:')
for i, r in enumerate(rows[:5]):
    try:
        steps = json.loads(r['steps_json'])
        steps_len = len(steps)
    except:
        steps_len = 0 if r['steps_json'].strip() == '[]' else -1
    print(f"  {r['case_id']}: status={r['deletion_status']}, steps_json_len={steps_len}")

# Verify targets
print('\n=== VERIFICATION ===')
print(f'Line count: {len(rows) + 1} (target: 519)')
print(f'Non-empty steps: {non_empty_count} (target: 424), diff: {non_empty_count - 424}')
print(f'Empty steps: {empty_count} (target: 94), diff: {empty_count - 94}')
print(f'DELETATION count: {deletation_count} (target: 0), diff: {deletation_count - 0}')