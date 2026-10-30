import os
import sys
import csv

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

USER_IDENTITIES = _load_csv("user_identities.csv")
USER_AUDIT_LOG = _load_csv("user_audit_log.csv")
SYSTEM_ACTIVITY = _load_csv("system_activity.csv")
DELETION_RULES = _load_csv("deletion_rules.csv")
EVIDENCE_FILES = _load_csv("evidence_files.csv")
DELETION_REQUESTS = _load_csv("deletion_requests.csv")

sys.path.insert(0, '.')
from core.llm_arbiter import _deterministic_classify

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

# Find NOT_APPLICABLE cases with no keywords
no_kw_cases = []
for r in DELETION_REQUESTS:
    case_id = r.get("case_id", "")
    rt_lower = r['request_text'].lower()
    
    has_non_del = any(kw in rt_lower for kw in non_del_keywords)
    has_del = any(kw in rt_lower for kw in del_keywords)
    cls = _deterministic_classify(r['request_text'])[0]
    rs = r.get('reported_status', '')
    
    if not has_non_del and not has_del:
        no_kw_cases.append((case_id, rs))

print(f"NOT_APPLICABLE cases with no keywords: {len(no_kw_cases)}")
print(f"\nreported_status distribution:")
rs_counts = {}
for case_id, rs in no_kw_cases:
    rs_counts[rs] = rs_counts.get(rs, 0) + 1
for k in sorted(rs_counts.keys()):
    print(f"  {k}: {rs_counts[k]}")

# Show case_ids with their reported_status
print(f"\nCase IDs and reported_status:")
for case_id, rs in no_kw_cases:
    print(f"  {case_id}: rs={rs}")