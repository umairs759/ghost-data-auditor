"""
Verification script for the Northstar Deletion Audit Agent.

Loads .env, tests connection to NVIDIA NIM API with a single test prompt,
and verifies that the output conforms to the AuditResult Pydantic model.
"""

from __future__ import annotations

import os
import sys
from typing import List

from dotenv import load_dotenv

from app.agent import DeletionAgent, AuditResult, RemediationStep
from app.logging import logger, log_system, log_error


def main() -> int:
    load_dotenv()
    log_system("Starting verify_agent.py")

    api_key = os.getenv("NVIDIA_API_KEY")
    base_url = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
    model = os.getenv("NVIDIA_MODEL", "meta/llama-3.3-70b-instruct")

    log_system(f"NVIDIA_BASE_URL={base_url}")
    log_system(f"NVIDIA_MODEL={model}")
    log_system(f"NVIDIA_API_KEY set: {bool(api_key)}")

    if not api_key:
        log_error("NVIDIA_API_KEY not set in .env; cannot test live API connection")
        print("SKIPPED: NVIDIA_API_KEY not configured")
        return 0

    # --- Test Pydantic model conformance --------------------------------- #
    test_step = RemediationStep(
        step_order=1,
        action="MANUAL_REVIEW",
        description="Test remediation step",
    )
    test_result = AuditResult(
        status="INCOMPLETE",
        exposed_records=["test_record_001"],
        active_sync_risks=[],
        remediation_steps=[test_step],
    )
    assert test_result.status == "INCOMPLETE"
    assert test_result.exposed_records == ["test_record_001"]
    assert test_result.active_sync_risks == []
    assert len(test_result.remediation_steps) == 1
    assert test_result.remediation_steps[0].action == "MANUAL_REVIEW"
    log_system("AuditResult Pydantic model conformance verified")

    # --- Test live NVIDIA NIM API connection ----------------------------- #
    agent = DeletionAgent(model=model, rules_path="deletion_rules.csv")

    test_identifiers: List[str] = ["user_12345"]
    test_snippets: List[dict] = [
        {
            "file_path": "data/test_user.txt",
            "extension": ".txt",
            "matches": [
                {
                    "type": "identifier",
                    "value": "user_12345",
                    "snippet": "user_12345 found in user data",
                }
            ],
        }
    ]

    try:
        result = agent.evaluate_deletion_context(
            identifiers=test_identifiers,
            snippets=test_snippets,
            rules=agent.rules,
        )
        # Verify output conforms to AuditResult schema.
        assert isinstance(result, AuditResult)
        assert result.status in ("COMPLETE", "INCOMPLETE", "NOT_APPLICABLE")
        assert isinstance(result.exposed_records, list)
        assert isinstance(result.active_sync_risks, list)
        assert isinstance(result.remediation_steps, list)
        log_system(
            f"Live API test passed: status={result.status}, "
            f"exposed_records={result.exposed_records}, "
            f"active_sync_risks={result.active_sync_risks}"
        )
        print(f"VERIFY OK: status={result.status}")
    except Exception as exc:  # noqa: BLE001
        log_error(f"Live API test failed: {exc}")
        print(f"VERIFY FAILED: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
