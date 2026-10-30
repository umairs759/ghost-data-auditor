import csv
import os

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
print(f"User identities: {len(USER_IDENTITIES)}")

DELETION_REQUESTS = _load_csv("deletion_requests.csv")
print(f"Deletion requests: {len(DELETION_REQUESTS)}")

if DELETION_REQUESTS:
    print(f"First: {DELETION_REQUESTS[0]}")