# Northstar Ghost Data Auditor - System Memory

## Overview
This system implements a Ghost Data Auditor that processes 518 deletion requests from 
`dataset/deletion_requests.csv` and generates `output.csv` with schema `case_id,deletion_status,steps_json`.

## Key Data Structures

### Deletion Request (per case)
- case_id: e.g., "case_33"
- email: User's email address
- requested_at: ISO-8601 timestamp
- reported_status: Claimed status (NOT_TRUSTED - never use directly)
- reported_at: When status was reported
- audit_at: **Ground truth timestamp** for state reconstruction
- request_text: Free-form user request

### Identity Resolution
- user_identities.csv: 850 entries mapping user_id -> name/email/phone
- user_audit_log.csv: 306 entries tracking historical email/phone changes
- Resolution maps any email/phone/username to set of user_ids

### System Activity
- system_activity.csv: 4011 chronological events across microservices
- Event types tracked: DELETE_RECORD, REDACT_RECORD, ANONYMIZE_RECORD,
  DISABLE_DATA_FLOW, BLOCK_RESTORE, SYNC_RECORD, LINK_RESOURCE_IDENTITY

### Deletion Rules
- deletion_rules.csv: 15 rules mapping data categories to required actions
- Rules define: Always DELETE, REDO, ANONYMIZE, RETAIN, BLOCK_RESTORE
- Example: rule_01 -> USER_PROFILE always DELETE; rule_05 -> SUPPORT_MESSAGE 
  redact if conversation contains shared context

### Evidence Files
- evidence_files.csv: 94 file manifest entries (file_id, file_path, origin, captured_at)
- Actual files in dataset/evidence/{databases,documents,images,logs,records}

## Pipeline Architecture

1. **load_all_data()**: Loads all CSV files and builds identity resolution indexes
2. **process_all_cases()**: Iterates through all 518 cases:
   - Classify request text (deterministic + optional LLM)
   - Resolve user identity from email
   - Replay activities up to audit_at
   - Determine deletion status (COMPLETE/INCOMPLETE/NOT_APPLICABLE)
   - Build steps_json with canonical ordering
3. **write_output_csv()**: Writes results sorted by case_id ascending

## Key Implementation Details

### State Reconstruction (at audit_at)
- Never trust reported_status - always reconstruct from actual events
- Track all state-changing events up to audit_at:
  - DELETE_RECORD, REDACT_RECORD, ANONYMIZE_RECORD
  - DISABLE_DATA_FLOW, BLOCK_RESTORE, SYNC_RECORD, LINK_RESOURCE_IDENTITY
- If active SYNC_RECORD or unblocked backup after deletion -> flag as Ghost Data

### Canonical Step Ordering
Phase order: FINDING(0) -> REMEDIATION(1) -> VERIFICATION(2)

FINDING operations: REPORT_REMAINING_RECORD -> REPORT_EXPOSED_PII -> 
REPORT_ACTIVE_DATA_FLOW -> REPORT_RESTORE_RISK

REMEDIATION operations: DISABLE_DATA_FLOW -> BLOCK_RESTORE -> 
DELETE_RECORD -> REDACT_RECORD -> ANONYMIZE_RECORD

VERIFICATION operations: VERIFY_RECORD_ABSENT -> VERIFY_RECORD_PRESENT -> 
VERIFY_RECORD_REDACTED -> VERIFY_RECORD_ANONYMIZED -> 
VERIFY_DATA_FLOW_DISABLED -> VERIFY_RESTORE_BLOCKED

Secondary sort: system_id ascending, resource_id ascending
Consecutive numbering: step_no starts at 1, increments by 1

### Evidence ID Binding
- COMPLETE: cite valid evidence_id (file_id, activity_id, or audit_id)
- INCOMPLETE: evidence_id = ""
- NOT_APPLICABLE: steps_json = []

### LLM Classification
- Model: nvidia/nemotron-3.3-70b-instruct (or configured model)
- Endpoint: https://integrate.api.nvidia.com/v1
- Context wrapped in <corpus_data>...</corpus_data> XML tags
- Tenacity exponential backoff: 4s, 8s, 16s, 32s, 60s (max 5 attempts)
- Fallback to deterministic keyword matching when LLM unavailable or fails

## Token Metrics (pending full LLM run)
- Current: 0 model calls (deterministic only)
- Estimated per-request cost: $0.30 (input) / $0.60 (output) for NIM model
- Full dataset: 518 cases, token tracking in evaluation/usage_report.md

## Files Structure

```
/code/
  main.py          # Master pipeline runner
  run_pipeline.py  # Convenience script
  evaluation/      # Evaluation reports
    evaluation_report.md
    usage_report.md
/core/
  identity_engine.py    # Identity resolution
  reconstruction_engine.py  # State reconstruction
  llm_arbiter.py        # NVIDIA NIM interface
  step_builder.py       # Canonical step ordering
/output.csv              # Generated output (519 lines)
/dataset/                # Input data
/app/                    # Dashboard (to be implemented)
```

## Known Issues & Hardening
- Deterministic classification may miss multilingual requests (LLM fallback available)
- Resource state reconstruction may miss some edge cases in activity replay
- Backup restore risk detection depends on complete SYNC_RECORD tracking
- Multilingual request classification improved with LLM (currently using deterministic + fallback)
- Step generation for INCOMPLETE cases ensures empty evidence_id for remediation steps