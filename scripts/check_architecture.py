"""Architecture boundary checker (no external deps).

Rules:
- domain/ must not import app, ui, screens
- services/ must not import ui, screens
- storage/ must not import ui, screens

Usage:
  python scripts/check_architecture.py
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RULES = {
    'domain': {'app', 'ui', 'screens'},
    'services': {'ui', 'screens'},
    'storage': {'ui', 'screens'},
}


def iter_py_files() -> list[Path]:
    skip_dirs = {'.pytest_cache', '__pycache__', 'build', 'dist', '.git', '.venv'}
    files: list[Path] = []
    for p in ROOT.rglob('*.py'):
        if any(part in skip_dirs for part in p.parts):
            continue
        files.append(p)
    return files


def layer_of(path: Path) -> str | None:
    rel = path.relative_to(ROOT)
    if not rel.parts:
        return None
    top = rel.parts[0]
    return top if top in RULES else None


def top_import_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Import):
        for alias in node.names:
            return alias.name.split('.')[0]
    if isinstance(node, ast.ImportFrom):
        if node.module:
            return node.module.split('.')[0]
    return None


def main() -> int:
    violations: list[str] = []
    for fpath in iter_py_files():
        layer = layer_of(fpath)
        if layer is None:
            continue
        try:
            tree = ast.parse(fpath.read_text(encoding='utf-8'), filename=str(fpath))
        except UnicodeDecodeError:
            tree = ast.parse(fpath.read_text(encoding='latin-1'), filename=str(fpath))
        forbidden = RULES[layer]
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            name = top_import_name(node)
            if name and name in forbidden:
                lineno = getattr(node, 'lineno', '?')
                violations.append(f"{layer}: {fpath.relative_to(ROOT)}:{lineno} imports '{name}'")

    if violations:
        print('Architecture boundary violations found:')
        for v in violations:
            print('  -', v)
        print('\nSee docs/ARCHITECTURE.md for the rules.')
        return 2

    print('OK: no architecture boundary violations found.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
