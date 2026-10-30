"""
Batch processing pipeline for the Northstar Deletion Audit Agent.

Reads deletion_requests.csv and deletion_rules.csv using pandas, iterates
through each request via auditor.process_deletion_request(), and exports
output.csv with the exact schema:
    request_id, status, exposed_records, active_sync_risks, remediation_steps

A corrupted row never halts the pipeline: it is logged, marked INCOMPLETE,
and processing continues.
"""

from __future__ import annotations

import csv
import json
import os
import sys
from typing import List, Optional

import pandas as pd

from app.auditor import DeletionAuditor
from app.logging import logger, log_system, log_error

REQUESTS_CSV = "deletion_requests.csv"
RULES_CSV = "deletion_rules.csv"
OUTPUT_CSV = "output.csv"
FIELDNAMES = [
    "request_id",
    "status",
    "exposed_records",
    "active_sync_risks",
    "remediation_steps",
]


def _find_file(filename: str) -> Optional[str]:
    """Look for a file in root, then dataset/ subdirectory."""
    if os.path.exists(filename):
        return filename
    dataset_path = os.path.join("dataset", filename)
    if os.path.exists(dataset_path):
        return dataset_path
    return None


def _create_dummy_requests_csv() -> str:
    """Create a dummy 2-row test dataset for end-to-end validation."""
    dummy_path = "deletion_requests.csv"
    dummy_content = (
        "request_id,user_id,email,identifier\n"
        "REQ-001,user_12345,alice@example.com,user_12345\n"
        "REQ-002,user_67890,bob@example.com,user_67890\n"
    )
    with open(dummy_path, "w", encoding="utf-8") as fh:
        fh.write(dummy_content)
    log_system(
        f"Created dummy test dataset at {dummy_path} for end-to-end validation"
    )
    return dummy_path


def _create_dummy_rules_csv() -> str:
    """Create a dummy rules file if none exists."""
    dummy_path = "deletion_rules.csv"
    dummy_content = (
        "rule_id,description\n"
        "RULE-001,All personal data must be deleted upon user request unless legally retained.\n"
        "RULE-002,Financial records must be retained for 7 years per tax regulations.\n"
    )
    with open(dummy_path, "w", encoding="utf-8") as fh:
        fh.write(dummy_content)
    log_system(f"Created dummy rules file at {dummy_path}")
    return dummy_path


def _make_incomplete_row(request_id: str, reason: str) -> dict:
    return {
        "request_id": str(request_id).strip() or "unknown",
        "status": "INCOMPLETE",
        "exposed_records": "[]",
        "active_sync_risks": "[]",
        "remediation_steps": json.dumps(
            [
                {
                    "step_order": 1,
                    "action": "manual_review",
                    "description": f"Pipeline error: {reason}. Manual review required.",
                }
            ],
            ensure_ascii=False,
        ),
    }


def main() -> int:
    log_system("Starting batch deletion audit pipeline")

    # --- Load requests ------------------------------------------------- #
    requests_path = _find_file(REQUESTS_CSV)
    if requests_path is None:
        log_system(
            "deletion_requests.csv not found in root or dataset/; "
            "creating dummy test dataset for validation"
        )
        requests_path = _create_dummy_requests_csv()

    try:
        requests_df = pd.read_csv(requests_path, dtype=str).fillna("")
        log_system(f"Loaded {len(requests_df)} requests from {requests_path}")
    except Exception as exc:  # noqa: BLE001
        log_error(f"Failed to read {requests_path}: {exc}")
        print(f"Failed to read {requests_path}: {exc}")
        return 1

    # --- Load rules ---------------------------------------------------- #
    rules_df = None
    rules_path = _find_file(RULES_CSV)
    if rules_path is not None:
        try:
            rules_df = pd.read_csv(rules_path, dtype=str).fillna("")
            log_system(f"Loaded {len(rules_df)} rules from {rules_path}")
        except Exception as exc:  # noqa: BLE001
            log_error(f"Failed to read {rules_path}: {exc}")
            rules_df = None
    else:
        log_system(
            "deletion_rules.csv not found in root or dataset/; "
            "creating dummy rules file"
        )
        rules_path = _create_dummy_rules_csv()
        try:
            rules_df = pd.read_csv(rules_path, dtype=str).fillna("")
            log_system(f"Loaded {len(rules_df)} rules from {rules_path}")
        except Exception as exc:  # noqa: BLE001
            log_error(f"Failed to read {rules_path}: {exc}")
            rules_df = None

    # --- Initialize auditor -------------------------------------------- #
    auditor = DeletionAuditor(
        corpus_path="data", rules_csv=RULES_CSV, sync_folder="scripts"
    )

    # --- Process each request ------------------------------------------ #
    results: List[dict] = []
    for _, row in requests_df.iterrows():
        row_dict = row.to_dict()
        try:
            result = auditor.process_deletion_request(row_dict, rules_df=rules_df)
        except Exception as exc:  # noqa: BLE001
            request_id = str(row_dict.get("request_id", "unknown")).strip()
            log_error(f"Unhandled error auditing {request_id}: {exc}")
            result = _make_incomplete_row(request_id, str(exc))

        # Guarantee schema fields exist.
        for field in FIELDNAMES:
            if field not in result:
                if field in ("exposed_records", "active_sync_risks"):
                    result[field] = "[]"
                elif field == "remediation_steps":
                    result[field] = "[]"
                else:
                    result[field] = ""
        results.append(result)
        log_system(
            f"Completed {result['request_id']} -> {result['status']} "
            f"(exposed={len(json.loads(result['exposed_records'])) if result['exposed_records'] else 0}, "
            f"sync_risks={len(json.loads(result['active_sync_risks'])) if result['active_sync_risks'] else 0})"
        )

    # --- Export output.csv --------------------------------------------- #
    try:
        out_df = pd.DataFrame(results, columns=FIELDNAMES)
        out_df.to_csv(
            OUTPUT_CSV, index=False, encoding="utf-8", quoting=csv.QUOTE_MINIMAL
        )
        log_system(f"Wrote {len(results)} rows to {OUTPUT_CSV}")
        print(f"Wrote {len(results)} rows to {OUTPUT_CSV}")
    except Exception as exc:  # noqa: BLE001
        log_error(f"Failed to write {OUTPUT_CSV}: {exc}")
        print(f"Failed to write {OUTPUT_CSV}: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
