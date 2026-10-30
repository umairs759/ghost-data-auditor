"""
Data discovery engine for the Northstar Deletion Audit Agent.

Recursively scans the local corpus directory for user identifiers (emails,
phone numbers, IDs) across text, JSON, CSV, and image (OCR) files. Strictly
sandboxed to the corpus directory via security.threat_model.secure_join.
A corrupted file is logged, skipped, and never halts the scan.
"""

from __future__ import annotations

import csv
import json
import os
import re
from typing import List, Optional

from PIL import Image
import pytesseract
from pytesseract import TesseractNotFoundError

from app.logging import logger, log_system
from security.threat_model import secure_join, sanitize_input


# Identifier regexes. Bounded and pre-compiled to avoid ReDoS.
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(
    r"\+?\d{1,3}[\s\-.]?\(?\d{2,4}\)?[\s\-.]?\d{3,4}[\s\-.]?\d{3,4}"
)
ID_RE = re.compile(
    r"\b(?:user.?id|uid|id|account.?no|customer.?id)[:\s=]+([A-Za-z0-9_-]{3,})\b",
    re.IGNORECASE,
)

TEXT_EXTENSIONS = {".txt", ".json", ".csv", ".log", ".md"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"}


class CorpusScanner:
    """Recursive file parser for text, JSON, CSV, and OCR (images)."""

    def __init__(self, corpus_path: str = "data"):
        self.corpus_path = os.path.abspath(corpus_path)
        os.makedirs(self.corpus_path, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Readers
    # ------------------------------------------------------------------ #
    def _read_text(self, file_path: str) -> str:
        """
        Read .txt, .json, .csv content with error handling (ignore decoding
        errors). JSON and CSV are flattened into searchable plain text.
        """
        ext = os.path.splitext(file_path)[1].lower()
        try:
            if ext == ".json":
                with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
                    data = json.load(fh)
                return self._json_to_text(data)
            if ext == ".csv":
                parts: List[str] = []
                with open(
                    file_path, "r", encoding="utf-8", errors="ignore", newline=""
                ) as fh:
                    reader = csv.reader(fh)
                    for row in reader:
                        parts.append(", ".join(row))
                return "\n".join(parts)
            # .txt / .log / .md
            with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
                return fh.read()
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to read text file %s: %s", file_path, exc)
            return ""

    @staticmethod
    def _json_to_text(data) -> str:
        """Recursively flatten a JSON structure into plain text."""
        parts: List[str] = []

        def walk(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    parts.append(str(key))
                    walk(value)
            elif isinstance(node, list):
                for item in node:
                    walk(item)
            else:
                parts.append(str(node))

        walk(data)
        return "\n".join(parts)

    def _read_image(self, file_path: str) -> str:
        """OCR an image file via pytesseract. Return '' on failure."""
        try:
            with Image.open(file_path) as img:
                return pytesseract.image_to_string(img)
        except FileNotFoundError as exc:
            log_system(
                f"Image file not found. Skipping OCR extraction for image: {file_path}"
            )
            return ""
        except TesseractNotFoundError as exc:
            log_system(
                f"Tesseract OCR binary not found. Skipping OCR extraction for image: {file_path}"
            )
            return ""
        except Exception as exc:  # noqa: BLE001
            logger.error("OCR failed for %s: %s", file_path, exc)
            return ""

    # ------------------------------------------------------------------ #
    # Public scan
    # ------------------------------------------------------------------ #
    def scan_directory(self, dir_path: str, identifiers_list: List[str]) -> List[dict]:
        """
        Recursively walk `dir_path` (sandboxed to self.corpus_path) and find
        files containing any identifier.

        Returns a list of dicts:
            {
                "file_path": str,
                "extension": str,
                "matches": [
                    {"type": str, "value": str, "snippet": str}, ...
                ]
            }
        Only files with at least one match are returned.
        """
        safe_dir = secure_join(self.corpus_path, dir_path)
        if safe_dir is None:
            logger.error("Path traversal blocked for directory %s", dir_path)
            return []
        if not os.path.isdir(safe_dir):
            logger.error("Directory does not exist: %s", safe_dir)
            return []

        results: List[dict] = []

        for root, _dirs, files in os.walk(safe_dir):
            for fname in files:
                file_path = os.path.join(root, fname)

                # Path-traversal defense on every file.
                if secure_join(self.corpus_path, file_path) != os.path.abspath(
                    file_path
                ):
                    logger.error("Path traversal blocked: %s", file_path)
                    continue

                ext = os.path.splitext(fname)[1].lower()
                if ext not in TEXT_EXTENSIONS and ext not in IMAGE_EXTENSIONS:
                    continue

                try:
                    if ext in IMAGE_EXTENSIONS:
                        content = self._read_image(file_path)
                    else:
                        content = self._read_text(file_path)
                except Exception as exc:  # noqa: BLE001
                    logger.error("Error reading %s: %s", file_path, exc)
                    continue

                if not content:
                    continue

                matches = self.search_identifiers(content, identifiers_list)
                if matches:
                    results.append(
                        {
                            "file_path": file_path,
                            "extension": ext,
                            "matches": matches,
                        }
                    )

        return results

    # ------------------------------------------------------------------ #
    # Identifier search
    # ------------------------------------------------------------------ #
    def search_identifiers(self, content: str, identifiers_list: List[str]) -> List[dict]:
        """
        Search `content` for emails, phone numbers, IDs, and any explicit
        identifiers from `identifiers_list`. Returns match dicts with snippets.
        """
        matches: List[dict] = []

        # Emails.
        for m in EMAIL_RE.finditer(content):
            matches.append(
                {
                    "type": "email",
                    "value": m.group(0),
                    "snippet": self._snippet(content, m.start(), m.end()),
                }
            )

        # Phone numbers.
        for m in PHONE_RE.finditer(content):
            matches.append(
                {
                    "type": "phone",
                    "value": m.group(0),
                    "snippet": self._snippet(content, m.start(), m.end()),
                }
            )

        # Generic IDs (user id / uid / id / account no / customer id).
        for m in ID_RE.finditer(content):
            matches.append(
                {
                    "type": "id",
                    "value": m.group(1) if m.lastindex else m.group(0),
                    "snippet": self._snippet(content, m.start(), m.end()),
                }
            )

        # Explicit user-provided identifiers (sanitized before regex).
        for ident in identifiers_list:
            safe_ident = sanitize_input(ident)
            if not safe_ident:
                continue
            try:
                pattern = re.compile(re.escape(safe_ident), flags=re.IGNORECASE)
            except re.error:
                continue
            for m in pattern.finditer(content):
                matches.append(
                    {
                        "type": "identifier",
                        "value": m.group(0),
                        "snippet": self._snippet(content, m.start(), m.end()),
                    }
                )

        return matches

    @staticmethod
    def _snippet(content: str, start: int, end: int, window: int = 80) -> str:
        """Return a short sanitized snippet around a match for context."""
        s = max(0, start - window)
        e = min(len(content), end + window)
        snippet = content[s:e].replace("\n", " ").strip()
        return sanitize_input(snippet)
