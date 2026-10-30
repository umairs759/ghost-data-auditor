# Ghost Data Still Exists — Deletion Audit Agent

## Overview

AI-powered deletion audit pipeline for the HackerRank Orchestrate October 2026
challenge ("Ghost Data Still Exists"). For each of 518 deletion requests, the agent
determines whether personal data is truly destroyed across databases, replicas, logs,
support attachments, search indexes, analytics exports, archives, and backups — or
whether ghost data remains.

## Architecture

```
dataset/              # Participant-facing input data (518 cases, identities, activity,
                      # rules, evidence)
code/main.py          # Entry point: hybrid deterministic + LLM pipeline
code/evaluation/      # evaluation_report.md, usage_report.md
output.csv            # Final predictions (518 rows)
log.txt               # Chat transcript & system logs
.env                  # NVIDIA API configuration (not committed)
```

### Hybrid Deterministic + LLM Pipeline

1. **Authorization check** — Deterministic keyword matching on `request_text`.
   Non-deletion requests (access, export, correction, marketing opt-out) → `NOT_APPLICABLE`.
   Ambiguous multilingual text → NVIDIA NIM LLM fallback.
2. **Identity resolution** — `user_identities.csv` (current snapshot) +
   `user_audit_log.csv` (historical email/phone changes) resolve all identifiers.
3. **Resource linking** — `LINK_RESOURCE_IDENTITY` activity events map identifiers
   to account, search, analytics, support, export, integration, and backup resources.
4. **State reconstruction** — At each case's `audit_at`, check `DELETE_RECORD`,
   `REDACT_RECORD`, `ANONYMIZE_RECORD`, `DISABLE_DATA_FLOW`, `BLOCK_RESTORE`
   events. Workflow `reported_status` is treated as a claim, not proof.
5. **Remediation planning** — Findings → Remediation → Verification, ordered per
   `problem_statement.md` §6.4. Evidence IDs cited for COMPLETE verification steps;
   empty `evidence_id` for INCOMPLETE remediation/future steps.

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure NVIDIA API key
cp .env.example .env
# Edit .env and set NVIDIA_API_KEY=your_key

# 3. Run the pipeline
python code/main.py

# 4. Output written to output.csv (518 rows)
```

## Run Command

```bash
python code/main.py
```

Produces `output.csv` at the repository root with schema:
`case_id,deletion_status,steps_json`

## Output Schema

| Column | Type | Description |
|--------|------|-------------|
| `case_id` | string | Case identifier |
| `deletion_status` | string | `COMPLETE`, `INCOMPLETE`, or `NOT_APPLICABLE` |
| `steps_json` | JSON string | Ordered array of step objects |

Each step object: `step_no`, `phase`, `system_id`, `resource_id`, `operation`,
`state`, `evidence_id`.

## Security

- API keys loaded from `.env` via `python-dotenv` (never hardcoded)
- No secrets in `code.zip` (`.env` excluded)
- No real personal data logged
- Deterministic where possible; LLM only for ambiguous cases

## Dependencies

- `openai` — NVIDIA NIM API client
- `python-dotenv` — Environment variable loading

See `code/evaluation/evaluation_report.md` and `code/evaluation/usage_report.md`
for evaluation metrics and token usage.
