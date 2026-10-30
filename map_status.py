import re
import sys

# Read output.csv raw content
with open('output.csv') as f:
    content = f.read()

# Read deletion_requests.csv raw content  
with open('dataset/deletion_requests.csv', encoding='utf-8', errors='replace') as f:
    dr_content = f.read()

# Build case_id -> reported_status mapping from deletion_requests
dr_rows = []
for line in dr_content.split('\n')[1:]:  # skip header
    parts = line.split(',', 6)  # at most 7 fields
    if len(parts) >= 7:
        case_id = parts[0]
        reported_status = parts[3]
        dr_rows.append((case_id, reported_status))

case_to_rs = {case_id: rs for case_id, rs in dr_rows}
print(f'Built mapping: {len(case_to_rs)} cases')

# Find NOT_APPLICABLE cases from output.csv
na_cases = []
for line in content.split('\n')[1:]:  # skip header
    # Format: case_id,deletion_status,steps_json
    # steps_json starts with [ so we can split on first comma after status
    # Actually, case_id is always at the start
    parts = line.split(',', 2)  # split into at most 3 parts
    if len(parts) >= 2:
        case_id = parts[0]
        status = parts[1]
        if status == 'NOT_APPLICABLE':
            rs = case_to_rs.get(case_id, 'UNKNOWN')
            na_cases.append((case_id, rs))

print(f'NOT_APPLICABLE cases: {len(na_cases)}')
print('\nNOT_APPLICABLE cases and their reported_status:')
for case_id, rs in na_cases:
    print(f'  {case_id}: rs={rs}')