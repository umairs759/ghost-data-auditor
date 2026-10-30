import csv
import json
import sys
import re

sys.path.insert(0, '.')
try:
    csv.field_size_limit(500 * 1024 * 1024)
except OverflowError:
    csv.field_size_limit(sys.maxsize // 10)

# Read output.csv
with open('output.csv') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

print(f'Total rows: {len(rows)}')

# Count current statuses
statuses = {}
for r in rows:
    s = r['deletion_status']
    statuses[s] = statuses.get(s, 0) + 1
print(f'Status counts: {statuses}')

empty = sum(1 for r in rows if r['steps_json'].strip() == '[]')
non_empty = sum(1 for r in rows if r['steps_json'].strip() != '[]')
print(f'Empty steps: {empty}, Non-empty: {non_empty}')

# Read deletion_requests.csv to get reported_status
with open('dataset/deletion_requests.csv', encoding='utf-8', errors='replace') as f:
    dr_content = f.read()

dr_rows = []
for line in dr_content.split('\n')[1:]:
    parts = line.split(',', 6)
    if len(parts) >= 7:
        case_id = parts[0]
        reported_status = parts[3]
        dr_rows.append((case_id, reported_status))

case_to_rs = {case_id: rs for case_id, rs in dr_rows}

# For each row, find the corresponding reported_status
# But steps_json can be large and contain commas, so simple split won't work
# Let me use regex to extract case_id and deletion_status from each line

# Build a mapping from case_id to the row index
case_to_row = {}
for i, r in enumerate(rows):
    case_to_row[r['case_id']] = i

# Check which COMPLETE/INCOMPLETE cases have no deletion keywords
# by looking at their request_text from the original data

# First, let's see the distribution of reported_status among each category
print('\nReported_status distribution by deletion_status:')
for status in ['COMPLETE', 'INCOMPLETE', 'NOT_APPLICABLE']:
    rs_dist = {}
    for r in rows:
        if r['deletion_status'] == status:
            case_id = r['case_id']
            rs = case_to_rs.get(case_id, 'UNKNOWN')
            rs_dist[rs] = rs_dist.get(rs, 0) + 1
    print(f'  {status}: {dict(rs_dist)}')

# Now let's look at NOT_APPLICABLE cases and their reported_status
print('\nNOT_APPLICABLE cases reported_status:')
na_rs = {}
for r in rows:
    if r['deletion_status'] == 'NOT_APPLICABLE':
        case_id = r['case_id']
        rs = case_to_rs.get(case_id, 'UNKNOWN')
        na_rs[rs] = na_rs.get(rs, 0) + 1
print(f'  Distribution: {dict(na_rs)}')

# COMPLETE cases reported_status
print('\nCOMPLETE cases reported_status:')
comp_rs = {}
for r in rows:
    if r['deletion_status'] == 'COMPLETE':
        case_id = r['case_id']
        rs = case_to_rs.get(case_id, 'UNKNOWN')
        comp_rs[rs] = comp_rs.get(rs, 0) + 1
print(f'  Distribution: {dict(comp_rs)}')

# INCOMPLETE cases reported_status
print('\nINCOMPLETE cases reported_status:')
inc_rs = {}
for r in rows:
    if r['deletion_status'] == 'INCOMPLETE':
        case_id = r['case_id']
        rs = case_to_rs.get(case_id, 'UNKNOWN')
        inc_rs[rs] = inc_rs.get(rs, 0) + 1
print(f'  Distribution: {dict(inc_rs)}')

# Check for no-keyword COMPLETE cases that are currently COMPLETE
# These are candidates for reclassification to NOT_APPLICABLE
non_del_keywords = [
    'unsubscribe', 'opt out', 'opt-out', 'marketing emails', 'marketing newsletters',
    'access my data', 'show me my data', 'data subject access request',
    'correct', 'update my info', 'fix my data', 'rectify',
    'export', 'data port', 'data portability', 'give me my data',
    'marketing opt-out', 'unsubscribe from'
]

del_keywords = [
    'delete', 'erase', 'remove my account', 'close my account',
    'right to be forgotten', 'permanent deletion', 'erase my data',
    'deletion', 'remove'
]

print('\n--- Analyzing COMPLETE cases for potential reclassification ---')
complete_candidates = []  # COMPLETE cases that might be better as NOT_APPLICABLE
for r in rows:
    if r['deletion_status'] == 'COMPLETE':
        case_id = r['case_id']
        rs = case_to_rs.get(case_id, 'UNKNOWN')
        # Check request text for keywords
        request_text = ''
        # Try to find request_text - need to parse the CSV properly
        # For now, just check the reported_status and other features
        complete_candidates.append((case_id, rs))

print(f'Total COMPLETE cases: {len(complete_candidates)}')

# Check INCOMPLETE cases
print('\n--- Analyzing INCOMPLETE cases for potential reclassification ---')
incomplete_candidates = []
for r in rows:
    if r['deletion_status'] == 'INCOMPLETE':
        incomplete_candidates.append(r['case_id'])

print(f'Total INCOMPLETE cases: {len(incomplete_candidates)}')

# Find cases where reported_status is COMPLETE but the request might not be a deletion request
print('\n--- COMPLETE cases with rs=COMPLETE that might be non-deletion ---')
potential_misclass = []
for r in rows:
    if r['deletion_status'] == 'COMPLETE':
        case_id = r['case_id']
        rs = case_to_rs.get(case_id, 'UNKNOWN')
        if rs == 'COMPLETE':
            # This case has rs=COMPLETE and is currently classified as COMPLETE
            # Check if it has deletion keywords
            # We'll check later
            potential_misclass.append((case_id, rs))

print(f'COMPLETE cases with rs=COMPLETE: {len(potential_misclass)}')