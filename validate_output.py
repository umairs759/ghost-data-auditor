"""
Validate output.csv integrity: schema, row count, statuses, JSON validity.
"""

from __future__ import annotations

import csv
import json
import sys

OUTPUT_CSV = "output.csv"
REQUESTS_CSV = "dataset/deletion_requests.csv"
VALID_STATUSES = {"COMPLETE", "INCOMPLETE", "NOT_APPLICABLE"}


def main() -> int:
    errors: list[str] = []

    # Load requests
    with open(REQUESTS_CSV, encoding="utf-8", errors="replace", newline="") as fh:
        requests = list(csv.DictReader(fh))
    request_count = len(requests)
    print(f"Requests: {request_count} rows")

    # Load output
    with open(OUTPUT_CSV, encoding="utf-8", errors="replace", newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        output_rows = list(reader)
    output_count = len(output_rows)
    print(f"Output: {output_count} rows")

    # 1. Row count
    if request_count != output_count:
        errors.append(f"Row count mismatch: requests={request_count}, output={output_count}")
    else:
        print(f"[PASS] Row count: {output_count}")

    # 2. Headers
    expected = ["case_id", "deletion_status", "steps_json"]
    if header != expected:
        errors.append(f"Header mismatch: expected={header}, actual={expected}")
    else:
        print(f"[PASS] Headers: {header}")

    # 3. Status values + JSON validity
    statuses_seen = set()
    for i, row in enumerate(output_rows):
        if len(row) != 3:
            errors.append(f"Row {i}: expected 3 columns, got {len(row)}")
            continue
        cid, status, steps = row
        statuses_seen.add(status)
        if status not in VALID_STATUSES:
            errors.append(f"Row {i} ({cid}): invalid status '{status}'")
        try:
            parsed = json.loads(steps)
            if not isinstance(parsed, list):
                errors.append(f"Row {i} ({cid}): steps_json not a list")
        except json.JSONDecodeError as exc:
            errors.append(f"Row {i} ({cid}): invalid JSON in steps_json: {exc}")

    print(f"[PASS] Statuses seen: {sorted(statuses_seen)}")
    print(f"[PASS] All steps_json are valid JSON arrays")

    # 4. Sorted by case_id
    case_ids = [row[0] for row in output_rows]
    if case_ids != sorted(case_ids):
        errors.append("Rows not sorted by case_id")
    else:
        print(f"[PASS] Rows sorted by case_id")

    # Summary
    print("=" * 50)
    if errors:
        print(f"VALIDATION FAILED: {len(errors)} error(s)")
        for e in errors[:20]:
            print(f"  - {e}")
        return 1
    print("VALIDATION PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
