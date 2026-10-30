import os
import sys
sys.path.insert(0, '.')

# Import from main
from code.main import load_all_data, DELETION_REQUESTS, OUTPUT_CSV

load_all_data()
print(f"DELETION_REQUESTS: {len(DELETION_REQUESTS)}")
if DELETION_REQUESTS:
    print(f"First: {DELETION_REQUESTS[0]}")