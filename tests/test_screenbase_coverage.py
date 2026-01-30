# -*- coding: utf-8 -*-
"""Architecture guard: ensure QWidget '*Screen' classes use ScreenBase.

This is a lightweight safety net to prevent regressions during refactors.

We intentionally ignore:
- QDialog-based screens (modal editors)
- QMainWindow/QWidget that are not named *Screen
"""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCREENS_DIR = ROOT / "screens"


def _iter_py_files():
    for p in SCREENS_DIR.rglob("*.py"):
        if p.name == "__init__.py":
            continue
        yield p


def _bases_to_names(bases):
    names = []
    for b in bases:
        if isinstance(b, ast.Name):
            names.append(b.id)
        elif isinstance(b, ast.Attribute):
            # e.g. QtWidgets.QDialog -> attr is QDialog
            names.append(b.attr)
    return names


def test_qwidget_screens_inherit_screenbase():
    offenders = []

    for path in _iter_py_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as e:
            offenders.append(f"{path.relative_to(ROOT)}::SYNTAX_ERROR({e})")
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue

            name = node.name
            if not name.endswith("Screen"):
                continue

            bases = _bases_to_names(node.bases)

            # Ignore QDialog screens
            if "QDialog" in bases:
                continue

            # If it directly declares ScreenBase, good.
            if "ScreenBase" in bases:
                continue

            # If it doesn't declare ScreenBase, flag it.
            offenders.append(f"{path.relative_to(ROOT)}::{name}({', '.join(bases)})")

    assert not offenders, "These Screen classes should inherit ScreenBase:\n" + "\n".join(offenders)
