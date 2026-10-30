# Northstar Ghost Data Auditor Refactor - Task Tracking

## Mission Status: IN PROGRESS

### Completed Tasks
- [x] **Dataset verification**: Confirmed presence of all dataset files
  - deletion_requests.csv (518 cases)
  - user_identities.csv (850 entries)
  - user_audit_log.csv (306 entries)
  - system_activity.csv (4011 events)
  - deletion_rules.csv (15 rules)
  - evidence_files.csv (94 files)
  - evidence/ directories (databases, documents, images, logs, records)

- [x] **core/identity_engine.py**: Built identity resolution graph
  - Maps emails/phones/usernames to canonical user_ids
  - Supports current and historical emails from audit log
  - Tested with 850 current emails, 212 old emails, 850 phone mappings

- [x] **core/reconstruction_engine.py**: State reconstruction at audit_at
  - Replays system_activity.csv per user identity
  - Cross-references with deletion_rules.csv
  - Detects restore risks from backups and active sync pipelines

- [x] **core/llm_arbiter.py**: NVIDIA NIM API interface
  - Classifies multilingual request_text to determine intent
  - Wraps context in <corpus_data>...</corpus_data> XML tags
  - Implements tenacity exponential backoff retries
  - Deterministic fallback when LLM unavailable

- [x] **core/step_builder.py**: Canonical step ordering
  - Strict FINDING -> REMEDIATION -> VERIFICATION phase ordering
  - Operation ordering within each phase
  - system_id ascending, then resource_id ascending secondary sort
  - Consecutive step_no numbering starting at 1
  - Evidence_id binding rules (COMPLETE/INCOMPLETE/NOT_APPLICABLE)

- [x] **code/main.py**: Master pipeline runner
  - Processes all 518 cases from deletion_requests.csv
  - Generates output.csv with schema: case_id,deletion_status,steps_json
  - Sorted by case_id ascending (519 lines including header)
  - Integrates all core modules

### In Progress Tasks
- [ ] **Output validation**: Verify output.csv against grader expectations
  - Current: 519 lines (correct), schema correct (correct)
  - Some cases generate empty steps_json - need to investigate

- [ ] **LLM integration**: Test NVIDIA NIM model calls
  - Currently using deterministic classification with LLM fallback
  - Requires NVIDIA_API_KEY environment variable

- [ ] **Dashboard creation**: Build interactive web interface
  - Planning Streamlit dashboard for case visualization

- [ ] **Evaluation reports**: Create evaluation_report.md and usage_report.md
  - Need to document case-level accuracy, step-level accuracy

### Remaining Tasks
- [ ] Fix step generation for cases with actual resource states
- [ ] Test and validate output.csv against HackerRank benchmarks
- [ ] Create interactive dashboard (streamlit run app/dashboard.py)
- [ ] Package code.zip with code/, README.md, and evaluation/
- [ ] Update log.txt with pipeline execution details
- [ ] Final score verification targeting 100/100

## Technical Notes

### Identity Resolution
- Current emails: 850 unique mappings
- Historical/old emails from audit log: 212 unique mappings
- Phone number mappings: 850 unique mappings
- Resolution uses build_identity_resolver() from core.identity_engine

### Deletion Status Classification
- DELETION: Request authorizes permanent deletion
- INCOMPLETE: Some records remain with active sync/restore risks
- NOT_APPLICABLE: Access/correction/export/marketing opt-out requests

### Step Ordering Law
1. Phase: FINDING -> REMEDIATION -> VERIFICATION
2. Operations within each phase in strict order
3. Secondary: system_id ascending, resource_id ascending
4. Consecutive step_no: 1, 2, 3, ...
5. Evidence ID: file_id for COMPLETE, "" for INCOMPLETE, [] for NOT_APPLICABLE