# -*- coding: utf-8 -*-
"""Section and action keys (single source of truth).

Keep these constants stable. They are used by:
- DataModel notify_section_changed(section)
- services.section_graph SECTION_GRAPH
- services.section_orchestrator mappings
- validation pipelines (by section)
"""

from __future__ import annotations

from enum import Enum


class Section(str, Enum):
    # data sections
    PROJECT = "project"
    INSTALACIONES = "instalaciones"
    CABINET = "cabinet"
    BOARD_FEED = "board_feed"
    CC = "cc"
    BANK_CHARGER = "bank_charger"
    DESIGNER = "designer"
    LOAD_TABLES = "load_tables"

    # synthetic events
    PROJECT_LOADED = "project_loaded"


class Refresh(str, Enum):
    MAIN = "main"
    INSTALACIONES = "instalaciones"
    CABINET = "cabinet"
    BOARD_FEED = "board_feed"
    CC = "cc"
    BANK_CHARGER = "bank_charger"
    DESIGNER = "designer"
    LOAD_TABLES = "load_tables"
