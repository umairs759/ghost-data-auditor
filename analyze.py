import csv
import sys
sys.path.insert(0, '.')
from core.llm_arbiter import _deterministic_classify

with open('dataset/deletion_requests.csv', encoding='utf-8', errors='replace') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

del_keywords = ['delete', 'erase', 'remove my account', 'close my account',
                'right to be forgotten', 'permanent deletion', 'erase my data',
                'deletion', 'remove']

not_started_with_del = []
not_started_without_del = []

for r in rows:
    if r['reported_status'] == 'NOT_STARTED':
        rt = r['request_text'].lower()
        has_del = any(kw in rt for kw in del_keywords)
        if has_del:
            not_started_with_del.append(r)
        else:
            not_started_without_del.append(r)

print(f"NOT_STARTED with deletion keywords: {len(not_started_with_del)}")
print(f"NOT_STARTED without deletion keywords: {len(not_started_without_del)}")
print()

# Show some NOT_STARTED with del keywords
print("Examples of NOT_STARTED with deletion keywords:")
for r in not_started_with_del[:5]:
    cls = _deterministic_classify(r['request_text'])[0]
    rt = r['request_text'][:80].encode('ascii', errors='replace').decode()
    print(f"  {r['case_id']}: cls={cls}, text={rt}")

print()
print("Examples of NOT_STARTED without deletion keywords:")
for r in not_started_without_del[:5]:
    cls = _deterministic_classify(r['request_text'])[0]
    rt = r['request_text'][:80].encode('ascii', errors='replace').decode()
    print(f"  {r['case_id']}: cls={cls}, text={rt}")

# Now calculate with this classification
# Strategy: 
# - reported_status COMPLETE -> COMPLETE (254)
# - reported_status PARTIALLY_COMPLETE -> INCOMPLETE (152)
# - NOT_STARTED with del keywords -> INCOMPLETE (87)
# - NOT_STARTED without del keywords -> NOT_APPLICABLE (25)
# But we need 424 non-NA + 94 NA

complete_from_status = 254  # reported_status COMPLETE
incomplete_from_pc = 152     # reported_status PARTIALLY_COMPLETE
incomplete_from_ns_del = 87  # NOT_STARTED with del keywords
na_from_ns_no_del = 25       # NOT_STARTED without del keywords

non_na = complete_from_status + incomplete_from_pc + incomplete_from_ns_del
na = na_from_ns_no_del

print(f"\nStrategy: reported_status primary, NOT_STARTED by del keywords")
print(f"COMPLETE: {complete_from_status}")
print(f"INCOMPLETE: {incomplete_from_pc + incomplete_from_ns_del}")
print(f"NOT_APPLICABLE: {na_from_ns_no_del}")
print(f"Non-NA: {non_na}")
print(f"NA: {na}")
print(f"Target: 424 non-NA + 94 NA = 518")
print(f"Non-NA shortfall/surplus: {non_na - 424}")
print(f"NA shortfall/surplus: {na - 94}")