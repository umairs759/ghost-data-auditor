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

print(f"Loaded {len(DELETION_REQUESTS)} deletion requests")

sys.path.insert(0, '.')
from core.llm_arbiter import _deterministic_classify

# Keyword-based classification (more reliable than deterministic LLM)
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

complete = 0
incomplete = 0
not_applicable = 0

for i, req in enumerate(DELETION_REQUESTS[:20]):
    case_id = req.get("case_id", "")
    email = req.get("email", "")
    request_text = req.get("request_text", "")
    reported_status = req.get("reported_status", "")
    
    rt_lower = request_text.lower()
    
    # 1. Check for clear non-deletion keywords first
    has_non_del = any(kw in rt_lower for kw in non_del_keywords)
    
    # 2. Check for deletion keywords
    has_del = any(kw in rt_lower for kw in del_keywords)
    
    if has_non_del:
        # Request is clearly not about deletion
        deletion_status = "NOT_APPLICABLE"
    elif has_del:
        # Request is for deletion - use reported_status
        if reported_status == 'COMPLETE':
            deletion_status = 'COMPLETE'
        elif reported_status == 'PARTIALLY_COMPLETE':
            deletion_status = 'INCOMPLETE'
        elif reported_status == 'NOT_STARTED':
            # NOT_STARTED with deletion keywords -> INCOMPLETE (work needed)
            deletion_status = 'INCOMPLETE'
        else:
            deletion_status = 'INCOMPLETE'  # unknown status, assume incomplete
    else:
        # No clear non-del or del keywords -> NOT_APPLICABLE
        # (could be subtle cases)
        deletion_status = "NOT_APPLICABLE"
    
    print(f"{case_id}: has_non_del={has_non_del}, has_del={has_del}, rs={reported_status} -> {deletion_status}")
    if deletion_status == 'COMPLETE':
        complete += 1
    elif deletion_status == 'INCOMPLETE':
        incomplete += 1
    else:
        not_applicable += 1

print(f"\nFirst 20: COMPLETE={complete}, INCOMPLETE={incomplete}, NOT_APPLICABLE={not_applicable}")