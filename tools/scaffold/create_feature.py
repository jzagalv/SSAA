# -*- coding: utf-8 -*-
"""Scaffold a new feature (calculation + validator + optional service).

Usage:
  python tools/scaffold/create_feature.py --name my_feature

Creates:
  - core/calculations/<name>.py
  - core/validators/<name>_validator.py
  - services/<name>_service.py

This tool is for development convenience only (not used at runtime).
"""

from __future__ import annotations

import argparse
import re
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def snake(name: str) -> str:
    name = name.strip().replace("-", "_")
    name = re.sub(r"\s+", "_", name)
    name = re.sub(r"[^a-zA-Z0-9_]+", "", name)
    return name.lower()


def ensure(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True, help="Feature name in snake_case (or will be converted)")
    args = ap.parse_args()

    n = snake(args.name)
    class_name = "".join([w.capitalize() for w in n.split("_") if w])

    calc = ROOT / "core" / "calculations" / f"{n}.py"
    val  = ROOT / "core" / "validators" / f"{n}_validator.py"
    svc  = ROOT / "services" / f"{n}_service.py"

    for p in (calc, val, svc):
        ensure(p)

    calc.write_text(textwrap.dedent(f"""        # -*- coding: utf-8 -*-
        \"\"\"{n} calculations (pure functions).

        Keep this module free of any UI or DataModel concerns.
        \"\"\"

        from __future__ import annotations

        from dataclasses import dataclass
        from typing import Any, Dict, List, Optional


        @dataclass
        class {class_name}Result:
            ok: bool = True
            warnings: List[str] = None
            data: Dict[str, Any] = None


        def compute_{n}(**kwargs) -> {class_name}Result:
            \"\"\"Main computation entrypoint for {n}.\"\"\"
            return {class_name}Result(ok=True, warnings=[], data={{}})
    """), encoding="utf-8")

    val.write_text(textwrap.dedent(f"""        # -*- coding: utf-8 -*-
        \"\"\"{n} validator (pure).

        Must not import UI. Should return domain Issues or simple strings.
        \"\"\"

        from __future__ import annotations

        from typing import Any, Dict, List


        def validate_{n}(data: Dict[str, Any]) -> List[str]:
            return []
    """), encoding="utf-8")

    svc.write_text(textwrap.dedent(f"""        # -*- coding: utf-8 -*-
        \"\"\"{n} service (thin wrapper).

        Optional: this module can orchestrate calculation + validation and integrate with DataModel.
        \"\"\"

        from __future__ import annotations

        from core.calculations.{n} import compute_{n}
        from core.validators.{n}_validator import validate_{n}


        def run_{n}(**kwargs):
            res = compute_{n}(**kwargs)
            issues = validate_{n}(res.data or {{}})
            return res, issues
    """), encoding="utf-8")

    print(f"Created: {calc}\nCreated: {val}\nCreated: {svc}")


if __name__ == "__main__":
    main()
