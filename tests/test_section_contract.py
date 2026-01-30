from __future__ import annotations

import re
from pathlib import Path


def _assert_section_decl(file_path: Path, expected: str) -> None:
    text = file_path.read_text(encoding="utf-8", errors="ignore")
    # Keep it simple: a readable, stable contract line.
    pattern = re.compile(r"^\s*SECTION\s*=\s*Section\.%s\s*$" % re.escape(expected), re.M)
    assert pattern.search(text), f"Missing SECTION = Section.{expected} in {file_path}"


def test_tab_screens_expose_section_contract():
    """All top-level tab screens must expose SECTION = Section.X.

    We validate via source text to avoid importing PyQt5 in CI/test environments.
    """

    root = Path(__file__).resolve().parents[1]
    _assert_section_decl(root / "screens/project/main_screen.py", "PROJECT")
    _assert_section_decl(root / "screens/project/location_screen.py", "INSTALACIONES")
    _assert_section_decl(root / "screens/cabinet/cabinet_screen.py", "CABINET")
    _assert_section_decl(root / "screens/board_feed/board_feed_screen.py", "BOARD_FEED")
    _assert_section_decl(root / "screens/load_tables/load_tables_screen.py", "LOAD_TABLES")
    _assert_section_decl(root / "screens/bank_charger/bank_charger_screen.py", "BANK_CHARGER")
    _assert_section_decl(root / "screens/ssaa_designer/ssaa_designer_screen.py", "DESIGNER")
    _assert_section_decl(root / "screens/cc_consumption/cc_consumption_screen.py", "CC")
