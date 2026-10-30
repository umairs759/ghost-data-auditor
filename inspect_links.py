import csv

# Check LINK_RESOURCE_IDENTITY events
with open('dataset/system_activity.csv', encoding='utf-8', errors='replace') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

links = [r for r in rows if r['event_type'] == 'LINK_RESOURCE_IDENTITY']
print(f'LINK_RESOURCE_IDENTITY events: {len(links)}')
for r in links[:10]:
    print(f"  {r['activity_id']} | {r['event_time']} | {r['source_system']} | {r['target_system']} | {r['resource_id']} | {r['reported_result']} | {r['details'][:100]}")

# Check what details look like for different event types
print("\n--- Sample details by event type ---")
for et in ['DELETE_RECORD', 'REDACT_RECORD', 'ANONYMIZE_RECORD', 'RETAIN_RECORD', 'SYNC_REDORD', 'SYNC_RECORD', 'RESTORE_BACKUP', 'CREATE_EXPORT']:
    evts = [r for r in rows if r['event_type'] == et]
    if evts:
        print(f"\n{et} ({len(evts)} events):")
        for r in evts[:3]:
            print(f"  {r['activity_id']} | {r['source_system']} -> {r['target_system']} | {r['resource_id']} | {r['reported_result']} | {r['details'][:120]}")
