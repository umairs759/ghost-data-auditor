import csv, json, sys
sys.path.insert(0, '.')
csv.field_size_limit(500*1024*1024)

with open('output.csv') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

# Line count
line_count = len(open('output.csv').read().splitlines())

# Headers
with open('output.csv') as f:
    header = f.readline().strip()

# Status counts
statuses = {}
for r in rows:
    s = r['deletion_status']
    statuses[s] = statuses.get(s, 0) + 1

# Empty vs non-empty
empty = sum(1 for r in rows if r['steps_json'].strip() == '[]')
non_empty = sum(1 for r in rows if r['steps_json'].strip() != '[]')

# DELETATION count
deletation_count = sum(1 for r in rows if 'DELETATION' in r['steps_json'])

# JSON validation
all_valid = True
for r in rows:
    steps = r['steps_json'].strip()
    if steps == '[]':
        continue
    try:
        json.loads(steps)
    except json.JSONDecodeError:
        all_valid = False

# Build result table
results = []
results.append(('Line count', line_count, 519))
results.append(('Header', header, 'case_id,deletion_status,steps_json'))
results.append(('NOT_APPLICABLE count', statuses.get('NOT_APPLICABLE', 0), 94))
results.append(('Empty steps_json []', empty, 94))
results.append(('Non-empty steps_json', non_empty, 424))
results.append(('DELETATION count', deletation_count, 0))
results.append(('All JSON valid', 'Yes' if all_valid else 'No', 'Yes'))

print('=' * 60)
print('FINAL VERIFICATION RESULTS')
print('=' * 60)
for name, actual, target in results:
    if isinstance(target, int):
        status = 'PASS' if actual == target else 'FAIL'
        print(f'  {name:30s}: {actual:5d} / {target:5d} - {status}')
    else:
        status = 'PASS' if actual == target else 'FAIL'
        print(f'  {name:30s}: {actual} - {status}')

print()
all_pass = all(actual == target for name, actual, target in results)
print(f'OVERALL: {"ALL TARGETS MET" if all_pass else "SOME TARGETS FAIL"}')