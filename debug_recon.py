import sys, os, json

# Add code directory to path
sys.path.insert(0, r'C:\Users\usamah\Desktop\Hackerrank_hackathon\code')

from code.main import load_all_data, parse_event_time
from core.identity_engine import resolve_identifiers
from core.reconstruction_engine import replay_activities_for_user

load_all_data()

# Check case_33
req = None
for r in DELETION_REQUESTS:
    if r.get('case_id') == 'case_33':
        req = r
        break

if not req:
    print('case_33 not found')
    import __main__
    __main__.sys.exit(1)

print('=== case_33 Debug ===')
the_email = req.get('email')
the_audit_at = req.get('audit_at')
the_request_text = req.get('request_text')[:80]

print('email:', the_email)
print('audit_at:', the_audit_at)
print('request_text:', the_request_text)

# Identity resolution
uids = resolve_identifiers(the_email, current_email_to_uids, old_email_to_uids, phone_to_uids)
print('Resolved uids:', uids)

if not uids:
    print('No uids resolved')
    sys.exit(1)

# Reconstruction
audit_at = parse_event_time(the_audit_at)
print('audit_at parsed:', audit_at)

recon = replay_activities_for_user(
    list(uids)[0],
    audit_at,
    SYSTEM_ACTIVITY,
    DELETION_RULES,
    current_email_to_uids,
    old_email_to_uids,
    phone_to_uids,
)

resource_states = recon.get('resource_states', {})
print('Resource states count:', len(resource_states))

if resource_states:
    items = list(resource_states.items())
    for i, (rid, info) in enumerate(items):
        if i >= 5:
            break
        state = info.get('state')
        reason = info.get('reason')
        rule = info.get('rule')
        print('  %d: %s -> %s (rule: %s)' % (i, rid, state, rule))
else:
    print('  NO resource states - investigating why...')
    canonical_uid = list(uids)[0]
    print('Canonical user ID:', canonical_uid)
    print('Total system activities:', len(SYSTEM_ACTIVITY))
    
    # Find events with this user ID
    user_str = canonical_uid
    count = 0
    for evt in SYSTEM_ACTIVITY:
        if user_str in str(evt):
            count += 1
    print('Events containing user ID:', count)
    for evt in SYSTEM_ACTIVITY[:5]:
        print('  ', evt.get('activity_id'), evt.get('event_type'), '->', evt.get('resource_id'))

# Also check how many cases have uids resolved
print('\n=== Checking uid resolution across cases ===')
resolved = 0
unresolved = 0
for r in DELETION_REQUESTS[:20]:
    u2 = resolve_identifiers(r.get('email', ''), current_email_to_uids, old_email_to_uids, phone_to_uids)
    if u2:
        resolved += 1
    else:
        unresolved += 1
        print('  UNRESOLVED:', r.get('case_id'), r.get('email'))
print('Resolved/unresolved in first 20:', resolved, unresolved)