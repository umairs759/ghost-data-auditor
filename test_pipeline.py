import os
import sys

# Test basic pipeline
ROOT = os.path.dirname(os.path.abspath('code/main.py'))
ROOT = os.path.join(ROOT, "..")
DATASET = os.path.join(ROOT, "dataset")

def _load_csv(filename):
    import csv
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

print(f"Deletion requests: {len(DELETION_REQUESTS)}")

sys.path.insert(0, '.')
from core.identity_engine import build_identity_resolver, resolve_identifiers

current_email_to_uids, old_email_to_uids, phone_to_uids, _, _ = build_identity_resolver(DATASET)
print(f"Identity resolver built")

# Test first case
req = DELETION_REQUESTS[0]
case_id = req.get("case_id", "")
email = req.get("email", "")
request_text = req.get("request_text", "")
reported_status = req.get("reported_status", "")

print(f"First case: {case_id}")
print(f"  Email: {email}")
print(f"  Request text: {request_text[:60]}...")
print(f"  Reported status: {reported_status}")

# Test classification
from core.llm_arbiter import _deterministic_classify
cls = _deterministic_classify(request_text)[0]
print(f"  Deterministic cls: {cls}")

non_del_kw = ['unsubscribe', 'opt out', 'opt-out', 'marketing emails', 'marketing newsletters',
    'access my data', 'show me my data', 'data subject access request',
    'correct', 'update my info', 'fix my data', 'rectify',
    'export', 'data port', 'data portability', 'give me my data',
    'marketing opt-out', 'unsubscribe from']
has_non_del = any(kw in request_text.lower() for kw in non_del_kw)
print(f"  Has non-del kw: {has_non_del}")

# Test resolve_identifiers
all_uids = resolve_identifiers(email, current_email_to_uids, old_email_to_uids, phone_to_uids)
print(f"  All UIDs: {all_uids}")
print(f"  Count: {len(all_uids)}")

if all_uids:
    canonical = list(all_uids)[0]
    print(f"  Canonical: {canonical}")