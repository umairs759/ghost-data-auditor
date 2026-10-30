# Strict Coding Rules
- **No Halts:** A corrupted row or file must NEVER halt the entire pipeline. Log to `log.txt`, assign INCOMPLETE or ERROR status to that row, and proceed.
- **Typed Data:** Use `Pydantic` for strict LLM output parsing to guarantee the CSV schema matches exactly.
- **Security First:** Sanitize all string inputs before regex searches to prevent ReDoS (Regular Expression Denial of Service).
