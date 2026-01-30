# -*- coding: utf-8 -*-
"""
Contract tests for scalability.

These tests are intentionally static (no Qt QApplication):
- Each screen module should declare a SECTION attribute
  so the refresh/orchestrator pipeline can work consistently.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCREENS = ROOT / "screens"

def _iter_screen_files():
    for p in SCREENS.rglob("*_screen.py"):
        yield p

def test_each_screen_declares_section_constant():
    missing = []
    for p in _iter_screen_files():
        txt = p.read_text(encoding="utf-8", errors="ignore")
        if "SECTION" not in txt:
            missing.append(str(p.relative_to(ROOT)))
    assert not missing, "Screens missing SECTION constant:\n- " + "\n- ".join(missing)
