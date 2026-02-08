# -*- coding: utf-8 -*-
"""Smoke test: import key SSAA modules to catch syntax/import errors."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path


MODULES = [
    "screens.ssaa_designer.widgets.feed_list_widget",
    "screens.ssaa_designer.widgets.exports",
    "screens.ssaa_designer.ssaa_designer_screen",
]


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    failed = []
    for mod in MODULES:
        try:
            importlib.import_module(mod)
        except Exception as exc:
            failed.append((mod, exc))

    if failed:
        for mod, exc in failed:
            print(f"[FAIL] {mod}: {exc}", file=sys.stderr)
        return 1

    print("[OK] smoke imports")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
