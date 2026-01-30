# -*- coding: utf-8 -*-
"""Regression tests: screens must be startup-safe.

We want to prevent a common class of bugs where a screen calls heavy refresh /
calculations inside __init__ (constructor). Those calls often assume that a
project is already loaded and can show modal dialogs or crash at startup.

Policy:
- __init__ may build UI and connect signals
- __init__ must NOT call reload_* / refresh_* / recalc_* methods
  (those are triggered by SectionOrchestrator via section_changed/project_loaded)
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _extract_init_block(py_path: Path) -> str:
    """Return the textual body of the first __init__ method found.

    This is a pragmatic parser (not AST): enough to prevent regressions.
    """

    txt = py_path.read_text(encoding="utf-8", errors="replace")
    lines = txt.splitlines()
    start = None
    indent = None
    for i, ln in enumerate(lines):
        if "def __init__(" in ln:
            start = i
            indent = len(ln) - len(ln.lstrip(" "))
            break
    if start is None:
        return ""
    # Body starts at next line
    body = []
    for ln in lines[start + 1 :]:
        if ln.strip().startswith("def ") and (len(ln) - len(ln.lstrip(" ")) <= indent):
            break
        body.append(ln)
    return "\n".join(body)


def test_no_heavy_calls_in_cc_consumption_init():
    p = ROOT / "screens" / "cc_consumption" / "cc_consumption_screen.py"
    block = _extract_init_block(p)
    assert "self.reload_data(" not in block
    assert "self.reload_from_project(" not in block


def test_no_heavy_calls_in_load_tables_init():
    p = ROOT / "screens" / "load_tables" / "load_tables_screen.py"
    block = _extract_init_block(p)
    assert "self.reload_from_project(" not in block
    assert "_refresh_ca(" not in block
    assert "_refresh_cc(" not in block


def test_no_heavy_calls_in_designer_init():
    p = ROOT / "screens" / "ssaa_designer" / "ssaa_designer_screen.py"
    block = _extract_init_block(p)
    # Designer may setup UI, but must not load topology from model during init.
    assert "self.reload_from_project(" not in block
