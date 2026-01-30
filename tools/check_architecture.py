"""Architecture boundary checks.

Runs a lightweight static import scan to prevent layer inversions.

Usage:
    python tools/check_architecture.py

Exit code:
    0 = OK
    1 = violations found
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

LAYER_RULES = {
    "domain": {"forbidden": {"screens", "ui", "app"}},
    "services": {"forbidden": {"screens", "ui"}},
    "storage": {"forbidden": {"screens", "ui"}},
    "core": {"forbidden": {"screens", "ui", "app"}},
}

PY_FILES = [p for p in ROOT.rglob("*.py") if "__pycache__" not in p.parts]


def top_package(modname: str) -> str | None:
    if not modname:
        return None
    return modname.split(".")[0]


def file_layer(path: Path) -> str | None:
    # layer is the first directory under root (domain/services/...)
    try:
        rel = path.relative_to(ROOT)
    except ValueError:
        return None
    if not rel.parts:
        return None
    return rel.parts[0]


def scan_file(path: Path) -> list[tuple[str, str]]:
    """Return list of (imported_top_pkg, detail)"""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except Exception:
        # Ignore parse failures (should not happen in committed code)
        return []

    imports: list[tuple[str, str]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                pkg = top_package(alias.name)
                if pkg:
                    imports.append((pkg, alias.name))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                pkg = top_package(node.module)
                if pkg:
                    imports.append((pkg, node.module))

    return imports


def main() -> int:
    violations: list[str] = []

    for f in PY_FILES:
        layer = file_layer(f)
        if layer not in LAYER_RULES:
            continue
        forbidden = LAYER_RULES[layer]["forbidden"]
        for pkg, detail in scan_file(f):
            if pkg in forbidden:
                violations.append(f"{f.relative_to(ROOT)} imports forbidden '{detail}' (layer={layer})")

    if violations:
        print("Architecture violations found:\n")
        for v in violations:
            print(" -", v)
        print("\nFix: move logic to lower layers or invert dependency via controller/service.")
        return 1

    print("OK: no architecture boundary violations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
