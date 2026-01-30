# -*- coding: utf-8 -*-
import re
from pathlib import Path

def test_controller_postload_refresh_delegates_to_orchestrator():
    p = Path(__file__).resolve().parents[1] / "app" / "controller.py"
    txt = p.read_text(encoding="utf-8", errors="replace")

    # Extract _refresh_after_project_load body (very lightweight check)
    m = re.search(r"def _refresh_after_project_load\(self\):(.+?)\n\s*def ", txt, flags=re.S)
    assert m, "Could not locate _refresh_after_project_load in controller.py"
    body = m.group(1)

    # Must call orchestrator
    assert "section_orchestrator.on_project_loaded" in body

    # Must not hardcode screen refreshes here
    forbidden = ["main_screen", "location_screen", "cabinet_screen", "board_feed_screen", "cc_screen", "bank_screen"]
    assert not any(f in body for f in forbidden), "Post-load refresh must be orchestrator-driven (no direct screen refreshes)."
