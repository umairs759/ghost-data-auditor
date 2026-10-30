"""
Central orchestration for the Northstar Deletion Audit Agent.

Ties the CorpusScanner and DeletionAgent together to process a single deletion
request, including sync-risk detection, and returns a structured dictionary
matching the final output.csv schema.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

import pandas as pd

from app.agent import DeletionAgent, AuditResult
from app.logging import logger, log_system, log_error
from app.scanner import CorpusScanner
from security.threat_model import secure_join, sanitize_input


# Config/sync filenames that may define jobs able to recreate deleted data.
SYNC_CONFIG_FILENAMES = {
    "crontab",
    "cron.txt",
    "sync.json",
    "sync.conf",
    "config.json",
    "config.yaml",
    "config.yml",
    "config.ini",
    "backup.json",
    "backup.conf",
    "cron",
    "crontab.bak",
}


class DeletionAuditor:
    def __init__(
        self,
        corpus_path: str = "data",
        rules_csv: str = "deletion_rules.csv",
        sync_folder: str = "scripts",
    ):
        self.corpus_path = os.path.abspath(corpus_path)
        self.scanner = CorpusScanner(self.corpus_path)
        self.agent = DeletionAgent(rules_path=rules_csv)
        self.sync_folder = os.path.abspath(sync_folder)

    # ------------------------------------------------------------------ #
    # Identifier extraction from a request row
    # ------------------------------------------------------------------ #
    @staticmethod
    def _extract_identifiers(request_row: Dict[str, Any]) -> List[str]:
        ids: List[str] = []
        for key in (
            "request_id",
            "user_id",
            "email",
            "identifier",
            "id",
            "username",
            "userId",
        ):
            val = request_row.get(key)
            if val is None:
                continue
            val = str(val).strip()
            if val and val not in ids:
                ids.append(val)
        return ids

    # ------------------------------------------------------------------ #
    # Sync-risk detection
    # ------------------------------------------------------------------ #
    def _scan_sync_jobs(self, identifiers: List[str]) -> List[str]:
        """
        Scan sync/config/cron files under the sync folder and corpus for
        references to any identifier. Returns a list of risk descriptions.
        """
        risks: List[str] = []
        search_roots: List[str] = []
        if os.path.isdir(self.sync_folder):
            search_roots.append(self.sync_folder)
        if os.path.isdir(self.corpus_path):
            search_roots.append(self.corpus_path)

        seen_paths: set = set()
        for root in search_roots:
            for dirpath, _dirs, files in os.walk(root):
                for fname in files:
                    if fname.lower() not in SYNC_CONFIG_FILENAMES:
                        continue
                    fpath = os.path.join(dirpath, fname)
                    abs_fpath = os.path.abspath(fpath)
                    if abs_fpath in seen_paths:
                        continue
                    seen_paths.add(abs_fpath)

                    # Sandbox check.
                    safe = secure_join(root, fpath)
                    if safe is None:
                        log_error(f"Path traversal blocked: {fpath}")
                        continue

                    try:
                        with open(fpath, "r", encoding="utf-8", errors="ignore") as fh:
                            content = fh.read()
                    except Exception as exc:  # noqa: BLE001
                        log_error(f"Cannot read sync config {fpath}: {exc}")
                        continue

                    for ident in identifiers:
                        safe_ident = sanitize_input(ident)
                        if not safe_ident:
                            continue
                        try:
                            pattern = re.compile(
                                re.escape(safe_ident), flags=re.IGNORECASE
                            )
                        except re.error:
                            continue
                        if pattern.search(content):
                            risks.append(
                                f"{fpath}: references identifier {ident}"
                            )

        return risks

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def process_deletion_request(
        self, request_row: Dict[str, Any], rules_df: Optional[pd.DataFrame] = None
    ) -> Dict[str, Any]:
        """
        Process a single deletion request end-to-end.

        Returns a dict with keys:
            request_id, status, exposed_records, active_sync_risks, remediation_steps
        """
        request_id = str(request_row.get("request_id", "unknown")).strip()
        log_system(f"Processing deletion request {request_id}")

        # 1. Extract identifiers.
        identifiers = self._extract_identifiers(request_row)

        # 2. Scan corpus for identifiers.
        try:
            file_matches = self.scanner.scan_directory(self.corpus_path, identifiers)
        except Exception as exc:  # noqa: BLE001
            log_error(f"Scanner failed for {request_id}: {exc}")
            file_matches = []

        exposed_records: List[str] = []
        for fm in file_matches:
            for m in fm.get("matches", []):
                exposed_records.append(m.get("value", ""))

        # 3. Sync-risk scan.
        sync_risks = self._scan_sync_jobs(identifiers)

        # 4. Convert rules_df to list of dicts for the agent.
        rules_list: List[dict] = []
        if rules_df is not None:
            try:
                rules_list = rules_df.to_dict(orient="records")
            except Exception as exc:  # noqa: BLE001
                log_error(f"Failed to convert rules_df: {exc}")

        # 5. NVIDIA agent evaluation.
        try:
            result: AuditResult = self.agent.evaluate_deletion_context(
                identifiers=identifiers,
                snippets=file_matches,
                rules=rules_list,
            )
        except Exception as exc:  # noqa: BLE001
            log_error(f"Agent failed for {request_id}: {exc}")
            result = AuditResult(
                status="INCOMPLETE",
                exposed_records=exposed_records,
                active_sync_risks=sync_risks,
                remediation_steps=[
                    {
                        "step_order": 1,
                        "action": "manual_review",
                        "description": f"Agent error: {exc}. Manual review required.",
                    }
                ],
            )

        # 6. Assemble output row matching the CSV schema exactly.
        # Serialize list columns as JSON strings to preserve structure and
        # avoid delimiter corruption in CSV.
        exposed_records_json = json.dumps(
            result.exposed_records if result.exposed_records else exposed_records,
            ensure_ascii=False,
        )
        sync_risks_combined = sync_risks + list(result.active_sync_risks)
        active_sync_risks_json = json.dumps(sync_risks_combined, ensure_ascii=False)
        remediation_steps_json = json.dumps(
            [
                {
                    "step_order": s.step_order,
                    "action": s.action,
                    "description": s.description,
                }
                for s in result.remediation_steps
            ],
            ensure_ascii=False,
        ) or "[]"

        return {
            "request_id": request_id,
            "status": result.status,
            "exposed_records": exposed_records_json,
            "active_sync_risks": active_sync_risks_json,
            "remediation_steps": remediation_steps_json,
        }
