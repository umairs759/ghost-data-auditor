# Product Requirements Document
**Goal:** Build a robust, AI-powered deletion audit pipeline that prevents "Ghost Data" by verifying data destruction across databases, logs, attachments, and backups.
**Inputs:** `deletion_requests.csv`, `deletion_rules.csv`, local media/text corpus.
**Core Logic:**
1. Extract user identifiers from requests.
2. Scan the file system (Regex + OCR for media) for identifiers.
3. Pass findings to NVIDIA LLM to differentiate between "legal retention" and "privacy leak" based on rules.
4. Scan cron/config files for sync jobs that could recreate data.
5. Output exact findings in `output.csv`.
