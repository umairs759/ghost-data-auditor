"""
Security utilities for the Northstar Deletion Audit Agent.

Provides:
    - secure_join(base, path): path-traversal defense using os.path.abspath
      and os.path.commonpath to guarantee resolution stays inside `base`.
    - sanitize_input(text): strip potentially malicious XML/HTML tags and
      control characters before data is sent to the LLM (prompt-injection
      defense).
"""

from __future__ import annotations

import os
import re
from typing import Optional


def secure_join(base: str, path: str) -> Optional[str]:
    """
    Join `base` with `path` and return the absolute path only if it resolves
    strictly inside `base`. Returns None if path traversal is detected.

    Uses os.path.abspath and os.path.commonpath to defeat "../" sequences,
    symlink tricks, mixed absolute/relative paths, and cross-drive escapes.
    """
    try:
        abs_base = os.path.abspath(base)
        abs_path = os.path.abspath(os.path.join(abs_base, path))
        common = os.path.commonpath([abs_base, abs_path])
        if common == abs_base:
            return abs_path
    except (ValueError, TypeError):
        # ValueError on Windows mixed drives; TypeError on non-string input.
        pass
    return None


def sanitize_input(text: str) -> str:
    """
    Strip potentially malicious XML/HTML constructs and control characters
    from user-controlled text before it is embedded in an LLM prompt.

    Removes:
        - XML processing instructions and declarations: <? ... ?>
        - CDATA sections: <![CDATA[ ... ]]>
        - HTML/XML comments: <!-- ... -->
        - All remaining tags: <tag ...>
        - Control characters except newline (\n) and tab (\t)
    Collapses runs of spaces/tabs introduced by tag removal.
    """
    if not isinstance(text, str):
        return ""

    result = text

    # XML processing instructions / declarations.
    result = re.sub(r"<\?[^>]*\?>", "", result)
    # CDATA blocks.
    result = re.sub(r"<!\[CDATA\[.*?\]\]>", "", result, flags=re.DOTALL)
    # HTML/XML comments.
    result = re.sub(r"<!--.*?-->", "", result, flags=re.DOTALL)
    # All remaining XML/HTML tags.
    result = re.sub(r"<[^>]+>", "", result)
    # Control characters except newline and tab.
    result = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", result)
    # Collapse whitespace introduced by tag removal.
    result = re.sub(r"[ \t]+", " ", result)
    return result.strip()
