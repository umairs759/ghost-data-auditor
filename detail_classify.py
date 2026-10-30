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

non_del_keywords = [
    'unsubscribe', 'opt out', 'opt-out', 'marketing emails', 'marketing newsletters',
    'access my data', 'show me my data', 'data subject access request',
    'correct', 'update my info', 'fix my data', 'rectify',
    'export', 'data port', 'data portability', 'give me my data',
    'marketing opt-out', 'unsubscribe from'
]

# Track NOT_APPLICABLE reasons
not_applicable_reasons = {
    'has_non_del_kw': 0,
    'cls_NOT_APPLICABLE': 0,
    'cls_ACCESS': 0,
    'cls_CORRECTION': 0,
    'cls_EXPORT': 0,
    'cls_MARKETING_OPT_OUT': 0,
    'other': 0,
}

not_applicable_with_del_kw = 0
not_applicable_but_del_request = 0

for r in DELETION_REQUESTS:
    cls = _deterministic_classify(r['request_text'])[0]
    rs = r.get('reported_status', '')
    rt = r['request_text'].lower()
    
    has_non_del = any(kw in rt for kw in non_del_keywords)
    
    if has_non_del:
        not_applicable_reasons['has_non_del_kw'] += 1
    elif cls == 'NOT_APPLICABLE':
        not_applicable_reasons['cls_NOT_APPLICABLE'] += 1
    elif cls == 'ACCESS':
        not_applicable_reasons['cls_ACCESS'] += 1
    elif cls == 'CORRECTION':
        not_applicable_reasons['cls_CORRECTION'] += 1
    elif cls == 'EXPORT':
        not_applicable_reasons['cls_EXPORT'] += 1
    elif cls == 'MARKETING_OPT_OUT':
        not_applicable_reasons['cls_MARKETING_OPT_OUT'] += 1
    else:
        not_applicable_reasons['other'] += 1
    
    # Check if it's a deletion request despite NOT_APPLICABLE classification
    del_keywords = ['delete', 'erase', 'remove my account', 'close my account',
                    'right to be forgotten', 'permanent deletion', 'erase my data',
                    'deletion', 'remove']
    has_del_kw = any(kw in rt for kw in del_keywords)
    
    if has_non_del:
        pass  # already counted
    elif cls != 'DELETION' and has_del_kw:
        not_applicable_but_del_request += 1
        if not_applicable_but_del_request <= 5:
            print(f"  NOT_APPLICABLE but has del keywords: {r['case_id']}: cls={cls}, rs={rs}, text={r['request_text'][:60]}")

print(f"NOT_APPLICABLE breakdown:")
for k, v in not_applicable_reasons.items():
    print(f"  {k}: {v}")
print(f"NOT_APPLICABLE but has deletion keywords: {not_applicable_but_del_request}")