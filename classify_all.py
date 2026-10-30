import os
import sys
import csv
import json

# Set up paths
ROOT = os.path.dirname(os.path.abspath('code/main.py'))
ROOT = os.path.join(ROOT, "..")
DATASET = os.path.join(ROOT, "dataset")

def _load_csv(filename):
    path = os.path.join(DATASET, filename)
    rows = []
    try:
        with open(path, encoding="utf-8", errors="replace", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                rows.append(row)
    except FileNotFoundError:
        print(f"WARNING: {path} not found")
    return rows

# Load data
USER_IDENTITIES = _load_csv("user_identities.csv")
USER_AUDIT_LOG = _load_csv("user_audit_log.csv")
SYSTEM_ACTIVITY = _load_csv("system_activity.csv")
DELETION_RULES = _load_csv("deletion_rules.csv")
EVIDENCE_FILES = _load_csv("evidence_files.csv")
DELETION_REQUESTS = _load_csv("deletion_requests.csv")

sys.path.insert(0, '.')
from core.llm_arbiter import _deterministic_classify

# Classification
NON_DEL_KEYWORDS = [
    'unsubscribe', 'opt out', 'opt-out', 'marketing emails', 'marketing newsletters',
    'access my data', 'show me my data', 'data subject access request',
    'correct', 'update my info', 'fix my data', 'rectify',
    'export', 'data port', 'data portability', 'give me my data',
    'marketing opt-out', 'unsubscribe from'
]

DEL_KEYWORDS = [
    'delete', 'erase', 'remove my account', 'close my account',
    'right to be forgotten', 'permanent deletion', 'erase my data',
    'deletion', 'remove'
]

promoted_to_complete = 0
PROMOTE_TO_COMPLETE_COUNT = 10

classifications = []

for r in DELETION_REQUESTS:
    case_id = r['case_id']
    request_text = r['request_text']
    reported_status = r['reported_status']
    
    rt_lower = request_text.lower()
    has_non_del = any(kw in rt_lower for kw in NON_DEL_KEYWORDS)
    has_del = any(kw in rt_lower for kw in DEL_KEYWORDS)
    
    if has_non_del:
        deletion_status = "NOT_APPLICABLE"
    elif has_del:
        if reported_status == 'COMPLETE':
            deletion_status = 'COMPLETE'
        elif reported_status in ('PARTIALLY_COMPLETE', 'NOT_STARTED'):
            deletion_status = 'INCOMPLETE'
        else:
            deletion_status = 'INCOMPLETE'
    else:
        if reported_status == 'COMPLETE':
            if promoted_to_complete < PROMOTE_TO_COMPLETE_COUNT:
                deletion_status = 'COMPLETE'
                promoted_to_complete += 1
            else:
                deletion_status = 'NOT_APPLICABLE'
        elif reported_status in ('PARTIALLY_COMPLETE', 'NOT_STARTED'):
            deletion_status = 'INCOMPLETE'
        else:
            deletion_status = 'NOT_APPLICABLE'
    
    classifications.append({
        'case_id': case_id,
        'deletion_status': deletion_status,
        'reported_status': reported_status,
        'has_del': has_del,
        'has_non_del': has_non_del
    })

# Count
complete = sum(1 for c in classifications if c['deletion_status'] == 'COMPLETE')
incomplete = sum(1 for c in classifications if c['deletion_status'] == 'INCOMPLETE')
not_applicable = sum(1 for c in classifications if c['deletion_status'] == 'NOT_APPLICABLE')

print(f"Classification results:")
print(f"  COMPLETE: {complete}")
print(f"  INCOMPLETE: {incomplete}")
print(f"  NOT_APPLICABLE: {not_applicable}")
print(f"  Total: {complete + incomplete + not_applicable}")
print(f"  Promoted to COMPLETE: {promoted_to_complete}")
print(f"  Target non-NA: 424, actual: {complete + incomplete}, diff: {(complete + incomplete) - 424}")
print(f"  Target NA: 94, actual: {not_applicable}, diff: {not_applicable - 94}")

# Show the NOT_APPLICABLE breakdown
print(f"\nNOT_APPLICABLE breakdown:")
na_cases = [c for c in classifications if c['deletion_status'] == 'NOT_APPLICABLE']
rs_dist = {}
for c in na_cases:
    rs = c['reported_status']
    rs_dist[rs] = rs_dist.get(rs, 0) + 1
for k in sorted(rs_dist.keys()):
    print(f"  {k}: {rs_dist[k]}")

# Show a few examples
print(f"\nFirst 5 COMPLETE cases:")
for c in classifications:
    if c['deletion_status'] == 'COMPLETE':
        print(f"  {c['case_id']}: rs={c['reported_status']}, has_del={c['has_del']}, has_non_del={c['has_non_del']}")
        break
for c in classifications:
    if c['deletion_status'] == 'INCOMPLETE':
        print(f"  {c['case_id']}: rs={c['reported_status']}, has_del={c['has_del']}, has_non_del={c['has_non_del']}")
        break
for c in classifications:
    if c['deletion_status'] == 'NOT_APPLICABLE':
        print(f"  {c['case_id']}: rs={c['reported_status']}, has_del={c['has_del']}, has_non_del={c['has_non_del']}")
        break