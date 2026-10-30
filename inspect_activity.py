import csv

with open('dataset/system_activity.csv', encoding='utf-8', errors='replace') as f:
    reader = csv.DictReader(f)
    rows = list(reader)
print(f'Total activity rows: {len(rows)}')
deletions = [r for r in rows if 'DELETE' in r['event_type'].upper()]
print(f'Delete-type events: {len(deletions)}')
for r in deletions[:10]:
    print(f"  {r['event_type']} | {r['source_system']} | {r['resource_id']} | {r['reported_result']}")

# Check for account deletions specifically
account_deletes = [r for r in rows if r['event_type'] == 'DELETE_RECORD' and 'account' in r['resource_id'].lower()]
print(f'\nAccount DELETE_RECORD events: {len(account_deletes)}')
for r in account_deletes[:5]:
    print(f"  {r['activity_id']} | {r['event_time']} | {r['resource_id']} | {r['reported_result']}")

# Check disable data flow
disable_flows = [r for r in rows if r['event_type'] == 'DISABLE_DATA_FLOW']
print(f'\nDISABLE_DATA_FLOW events: {len(disable_flows)}')
for r in disable_flows[:5]:
    print(f"  {r['activity_id']} | {r['source_system']} | {r['resource_id']} | {r['reported_result']}")

# Check block restore
block_restores = [r for r in rows if r['event_type'] == 'BLOCK_RESTORE']
print(f'\nBLOCK_RESTORE events: {len(block_restores)}')
for r in block_restores[:5]:
    print(f"  {r['activity_id']} | {r['source_system']} | {r['resource_id']} | {r['reported_result']}")
