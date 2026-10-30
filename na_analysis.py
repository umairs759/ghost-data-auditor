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

# Find NOT_APPLICABLE cases and why
na_cases = []
for r in DELETION_REQUESTS:
    case_id = r.get("case_id", "")
    rt_lower = r['request_text'].lower()
    
    has_non_del = any(kw in rt_lower for kw in non_del_keywords)
    has_del = any(kw in rt_lower for kw in del_keywords)
    cls = _deterministic_classify(r['request_text'])[0]
    rs = r.get('reported_status', '')
    
    if not has_non_del and not has_del:
        # This case has neither non-del nor del keywords
        na_cases.append((case_id, "no_keywords", cls, rs))
    elif has_non_del and not has_del:
        na_cases.append((case_id, "has_non_del_only", cls, rs))
    elif not has_non_del and has_del:
        na_cases.append((case_id, "has_del_only", cls, rs))
    elif has_non_del and has_del:
        na_cases.append((case_id, "has_both", cls, rs))

print(f"NOT_APPLICABLE cases breakdown:")
no_kw = sum(1 for c in na_cases if c[1] == "no_keywords")
has_non = sum(1 for c in na_cases if c[1] == "has_non_del_only")
has_del = sum(1 for c in na_cases if c[1] == "has_del_only")
has_both = sum(1 for c in na_cases if c[1] == "has_both")

print(f"  no_keywords: {no_kw}")
print(f"  has_non_del_only: {has_non}")
print(f"  has_del_only: {has_del}")
print(f"  has_both: {has_both}")

print(f"\nNOT_APPLICABLE cases with has_del_only (should potentially be INCOMPLETE):")
for c in na_cases:
    if c[1] == "has_del_only":
        print(f"  {c[0]}: rs={c[3]}, cls={c[2]}, text={c[0][:80] if len(c) > 80 else c[0]}")

# Show first few
print(f"\nFirst 10 NOT_APPLICABLE cases:")
for c in na_cases[:10]:
    print(f"  {c[0]}: {c[1]}, rs={c[3]}, cls={c[2]}")