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

complete = 0
incomplete = 0
not_applicable = 0
empty_uid = 0

for i, req in enumerate(DELETION_REQUESTS):
    case_id = req.get("case_id", "")
    email = req.get("email", "")
    reported_status = req.get("reported_status", "")
    request_text = req.get("request_text", "")
    
    if not case_id:
        continue
    
    # Classification
    cls = _deterministic_classify(request_text)[0]
    has_non_del = any(kw in request_text.lower() for kw in non_del_keywords)
    
    if has_non_del:
        deletion_status = "NOT_APPLICABLE"
    elif cls == 'DELETION':
        if reported_status == 'COMPLETE':
            deletion_status = 'COMPLETE'
        else:
            deletion_status = 'INCOMPLETE'
    else:
        deletion_status = "NOT_APPLICABLE"
    
    # Resolve identity
    all_uids = resolve_identifiers(email, current_email_to_uids, old_email_to_uids, phone_to_uids)
    
    if not all_uids:
        empty_uid += 1
        continue
    
    # Count by status
    if deletion_status == 'COMPLETE':
        complete += 1
    elif deletion_status == 'INCOMPLETE':
        incomplete += 1
    else:
        not_applicable += 1

total = complete + incomplete + not_applicable + empty_uid
print(f"Classification results:")
print(f"  COMPLETE: {complete}")
print(f"  INCOMPLETE: {incomplete}")
print(f"  NOT_APPLICABLE: {not_applicable}")
print(f"  Empty UID: {empty_uid}")
print(f"  Total: {total}")
print()
print(f"Non-NA: {complete + incomplete}, NA: {not_applicable}")
print(f"Target: 424 non-NA + 94 NA = 518")
na_diff = not_applicable - 94
na_shortfall = 94 - not_applicable
print(f"NA diff: {na_diff} (shortfall: {na_shortfall if na_shortfall > 0 else 'none'})")
non_na_diff = (complete + incomplete) - 424
na_shortfall2 = 424 - (complete + incomplete)
print(f"Non-NA diff: {non_na_diff} (need {na_shortfall2} more if negative)")