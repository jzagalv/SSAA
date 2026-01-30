# -*- coding: utf-8 -*-
"""
Create a new screen module from templates.

Usage (from repo root):
    python tools/scaffold/create_screen.py --name "Load Flow" --module load_flow --section LOAD_TABLES

This will create:
  screens/<module>/
    __init__.py
    <module>_screen.py
    <module>_controller.py

Note: adjust controller.py to register the screen.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "tools" / "scaffold" / "templates" / "screen"

def pascal(s: str) -> str:
    parts = re.split(r"[^a-zA-Z0-9]+", s.strip())
    return "".join(p[:1].upper() + p[1:] for p in parts if p)

def render(t: str, ctx: dict) -> str:
    for k, v in ctx.items():
        t = t.replace("{{"+k+"}}", v)
    return t

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True, help="Human name, e.g. 'Load Flow'")
    ap.add_argument("--module", required=True, help="python module name, e.g. load_flow")
    ap.add_argument("--section", required=True, help="Section enum member, e.g. PROJECT or CABINET")
    args = ap.parse_args()

    screen_module = args.module.strip().lower()
    screen_class = pascal(screen_module) + "Screen"
    controller_class = pascal(screen_module) + "Controller"
    section_enum = args.section.strip().upper()

    out_dir = ROOT / "screens" / screen_module
    out_dir.mkdir(parents=True, exist_ok=False)

    ctx = {
        "screen_module": screen_module,
        "screen_class": screen_class,
        "controller_class": controller_class,
        "section_enum": section_enum,
    }

    (out_dir / "__init__.py").write_text(render((TEMPLATES/"__init__.py.tmpl").read_text(encoding="utf-8"), ctx), encoding="utf-8")
    (out_dir / f"{screen_module}_screen.py").write_text(render((TEMPLATES/"{{screen_module}}_screen.py.tmpl").read_text(encoding="utf-8"), ctx), encoding="utf-8")
    (out_dir / f"{screen_module}_controller.py").write_text(render((TEMPLATES/"{{screen_module}}_controller.py.tmpl").read_text(encoding="utf-8"), ctx), encoding="utf-8")

    print(f"Created screen at: {out_dir}")
    print("Next steps:")
    print("- Register the screen in app/controller.py (create + add to tab stack)")
    print("- Add section refresh wiring (orchestrator) if applicable")

if __name__ == "__main__":
    main()
