# -*- coding: utf-8 -*-
"""Guardrail: avoid reintroducing `.value` usage for Section/Refresh inside app/services."""

from __future__ import annotations

import os
import re

EXEMPT_FILES = {
    os.path.join("services", "validation_service.py"),
    os.path.join("app", "section_catalog.py"),
}

PATTERNS = [
    re.compile(r"\b(sec|ref|section|refresh)\.value\b"),
    re.compile(r"\bSection\.[A-Z0-9_]+\.value\b"),
    re.compile(r"\bRefresh\.[A-Z0-9_]+\.value\b"),
]

def test_no_internal_section_refresh_value_usage():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    for folder in ("app", "services"):
        base = os.path.join(root, folder)
        for dirpath, _, filenames in os.walk(base):
            for fn in filenames:
                if not fn.endswith(".py"):
                    continue
                rel = os.path.relpath(os.path.join(dirpath, fn), root)
                if rel in EXEMPT_FILES:
                    continue
                with open(os.path.join(root, rel), "r", encoding="utf-8") as f:
                    for lineno, line in enumerate(f, 1):
                        for pat in PATTERNS:
                            if pat.search(line):
                                raise AssertionError(f"Forbidden `.value` usage in {rel}:{lineno}: {line.strip()}")
