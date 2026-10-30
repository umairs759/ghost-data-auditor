import csv
with open('dataset/deletion_requests.csv', encoding='utf-8', errors='replace') as f:
    reader = csv.DictReader(f)
    rows = list(reader)
    print(f'Total rows: {len(rows)}')
    print(f'First row: {rows[0]}')
    # Check unique statuses
    statuses = set(r['reported_status'] for r in rows)
    print(f'Reported statuses: {statuses}')
    # Check for NOT_STARTED, PARTIALLY_COMPLETE
    ns = [r for r in rows if r['reported_status'] == 'NOT_STARTED']
    pc = [r for r in rows if r['reported_status'] == 'PARTIALLY_COMPLETE']
    print(f'NOT_STARTED: {len(ns)}')
    print(f'PARTIALLY_COMPLETE: {len(pc)}')