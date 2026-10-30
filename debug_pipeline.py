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

print(f"Loaded {len(DELETION_REQUESTS)} deletion requests")
print(f"Loaded {len(SYSTEM_ACTIVITY)} system activity events")
print(f"Loaded {len(EVIDENCE_FILES)} evidence files")
print(f"Loaded {len(USER_IDENTITIES)} user identities")

sys.path.insert(0, '.')
from core.identity_engine import build_identity_resolver, resolve_identifiers

current_email_to_uids, old_email_to_uids, phone_to_uids, \
    user_id_to_canonical, user_id_aliases = build_identity_resolver(DATASET)

print(f"Built identity resolution indexes")
print(f"current_email_to_uids entries: {len(current_email_to_uids)}")
print(f"phone_to_uids entries: {len(phone_to_uids)}")

# Test resolving one email
test_email = DELETION_REQUESTS[0]['email']
all_uids = resolve_identifiers(test_email, current_email_to_uids, old_email_to_uids, phone_to_uids)
print(f"Resolved email {test_email}: {len(all_uids)} uids: {list(all_uids)[:5]}")

# Now test classification
from core.llm_arbiter import _deterministic_classify
r = DELETION_REQUESTS[0]
cls = _deterministic_classify(r['request_text'])[0]
print(f"Deterministic classification: {cls}")
print(f"reported_status: {r['reported_status']}")

# Test the classification logic
non_del_keywords = [
    'unsubscribe', 'opt out', 'opt-out', 'marketing emails', 'marketing newsletters',
    'access my data', 'show me my data', 'data subject access request',
    'correct', 'update my info', 'fix my data', 'rectify',
    'export', 'data port', 'data portability', 'give me my data',
    'marketing opt-out', 'unsubscribe from'
]
has_non_del = any(kw in r['request_text'].lower() for kw in non_del_keywords)
print(f"Has non-del keywords: {has_non_del}")

if cls == 'DELETION':
    if r['reported_status'] == 'COMPLETE':
        deletion_status = 'COMPLETE'
    else:
        deletion_status = 'INCOMPLETE'
    print(f"deletion_status: {deletion_status}")