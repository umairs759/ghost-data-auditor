#!/usr/bin/env python
import sys
import os

sys.path.insert(0, r'C:\Users\usamah\Desktop\Hackerrank_hackathon\code')
os.chdir(r'C:\Users\usamah\Desktop\Hackerrank_hackathon')

from main import load_all_data, process_all_cases, write_output_csv

# Load data
load_all_data()

# Process all cases
print("Processing all 518 cases...")
results = process_all_cases()

# Write output CSV
write_output_csv(results, os.path.join('output.csv'))

# Print summary
from collections import Counter
status_counts = Counter(r.get('deletion_status') for r in results)
total_steps = sum(len(r.get('steps_json', [])) for r in results)

print(f"\n{'='*60}")
print(f"Processing complete!")
print(f"{'='*60}")
print(f"Total cases: {len(results)}")
for status, count in sorted(status_counts.items()):
    print(f"  {status}: {count}")
print(f"Total steps generated: {total_steps}")
print(f"Output written to: {os.path.join(os.getcwd(), 'output.csv')}")
PYEOF