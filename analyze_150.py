import csv
import os
import sys

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
from core.identity_engine import build_identity_resolver, resolve_identifiers
from core.llm_arbiter import _deterministic_classify

current_email_to_uids, old_email_to_uids, phone_to_uids, _, _ = build_identity_resolver(DATASET)

del_keywords = ['delete', 'erase', 'remove my account', 'close my account',
                'right to be forgotten', 'permanent deletion', 'erase my data',
                'deletion', 'remove']

non_del_keywords = [
    'unsubscribe', 'opt out', 'opt-out', 'marketing emails', 'marketing newsletters',
    'access my data', 'show me my data', 'data subject access request',
    'correct', 'update my info', 'fix my data', 'rectify',
    'export', 'data port', 'data portability', 'give me my data',
    'marketing opt-out', 'unsubscribe from'
]

# Find NOT_APPLICABLE cases that have deletion keywords
na_with_del = []
for r in DELETION_REQUESTS:
    cls = _deterministic_classify(r['request_text'])[0]
    rs = r.get('reported_status', '')
    rt = r['request_text'].lower()
    
    has_non_del = any(kw in rt for kw in non_del_keywords)
    has_del_kw = any(kw in rt for kw in del_keywords)
    
    if not has_non_del and not has_del_kw:
        continue  # skip, these are the "clean" NOT_APPLICABLE
    
    if has_non_del:
        continue  # skip, these have non-del keywords
    
    # Not has_non_del and has_del_kw -> NOT_APPLICABLE but has del keywords
    na_with_del.append(r)

print(f"NOT_APPLICABLE but has deletion keywords: {len(na_with_del)}")

# Count by reported_status
rs_counts = {}
for r in na_with_del:
    rs = r['reported_status']
    rs_counts[rs] = rs_counts.get(rs, 0) + 1

print(f"reported_status distribution: {rs_counts}")

# Show a few examples
print("\nExamples:")
for r in na_with_del[:5]:
    cls = _deterministic_classify(r['request_text'])[0]
    print(f"  {r['case_id']}: rs={rs}, cls={cls}, text={r['request_text'][:70]}")

# Also check: of the NOT_APPLICABLE without del keywords, how many have non-del keywords?
na_without_del = []
for r in DELETION_REQUESTS:
    cls = _deterministic_classify(r['request_text'])[0]
    rs = r.get('reported_status', '')
    rt = r['request_text'].lower()
    
    has_non_del = any(kw in rt for kw in non_del_keywords)
    has_del_kw = any(kw in rt for kw in del_keywords)
    
    if not has_non_del and not has_del_kw:
        na_without_del.append(r)

print(f"\nNOT_APPLICABLE without deletion keywords: {len(na_without_del)}")

# Show a few
print("\nExamples of NOT_APPLICABLE without del keywords:")
for r in na_without_del[:5]:
    cls = _deterministic_classify(r['request_text'])[0]
    print(f"  {r['case_id']}: rs={rs}, cls={cls}, text={r['request_text'][:70]}")

# Check how many of na_without_del have rs=COMPLETE, PARTIALLY_COMPLETE, NOT_STARTED
rs_dist = {}
for r in na_without_del:
    rs = r['reported_status']
    rs_dist[rs] = rs_dist.get(rs, 0) + 1
print(f"reported_status distribution (no del keywords): {rs_dist}")