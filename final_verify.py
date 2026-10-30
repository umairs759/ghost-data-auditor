import csv, json, sys
sys.path.insert(0, '.')
csv.field_size_limit(500*1024*1024)

with open('output.csv') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

print('=== FINAL VERIFICATION ===')
print()

# 1. Line count
line_count = len(open('output.csv').read().splitlines())
result1 = "PASS" if line_count == 519 else "FAIL"
print(f'1. Line count: {line_count} (target: 519) - {result1}')

# 2. Headers
with open('output.csv') as f:
    header = f.readline().strip()
result2 = "PASS" if header == "case_id,deletion_status,steps_json" else "FAIL"
print(f'2. Header: {header} (target: case_id,deletion_status,steps_json) - {result2}')

# 3. Status counts
statuses = {}
for r in rows:
    s = r['deletion_status']
    statuses[s] = statuses.get(s, 0) + 1
print(f'3. Status counts: {statuses}')
not_applicable_count = statuses.get("NOT_APPLICABLE", 0)
result3 = "PASS" if not_applicable_count == 94 else "FAIL"
print(f'   NOT_APPLICABLE: {not_applicable_count} (target: 94) - {result3}')

# 4. Empty vs non-empty steps_json
empty = sum(1 for r in rows if r['steps_json'].strip() == '[]')
non_empty = sum(1 for r in rows if r['steps_json'].strip() != '[]')
result4_empty = "PASS" if empty == 94 else "FAIL"
result4_non_empty = "PASS" if non_empty == 424 else "FAIL"
print(f'4. Empty steps_json: []: {empty} (target: 94) - {result4_empty}')
print(f'   Non-empty steps_json: {non_empty} (target: 424) - {result4_non_empty}')

# 5. DELETATION count
deletation_count = sum(1 for r in rows if 'DELETATION' in r['steps_json'])
result5 = "PASS" if deletation_count == 0 else "FAIL"
print(f'5. DELETATION count: {deletation_count} (target: 0) - {result5}')

# 6. JSON parsing validation
all_valid = True
for r in rows:
    steps = r['steps_json'].strip()
    if steps == '[]':
        continue
    try:
        json.loads(steps)
    except json.JSONDecodeError:
        all_valid = False
        print(f'   INVALID JSON in {r["case_id"]}')
result6 = "PASS" if all_valid else "FAIL"
print(f'6. All JSON objects parse without errors - {result6}')

print()
if line_count == 519 and header == "case_id,deletion_status,steps_json" and not_applicable_count == 94 and empty == 94 and non_empty == 424 and deletation_count == 0 and all_valid:
    print('OVERALL: ALL TARGETS MET')
else:
    print('OVERALL: SOME TARGETS FAIL')