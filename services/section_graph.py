# -*- coding: utf-8 -*-
"""Declarative section dependency graph.

This prevents cross-screen "hydra wiring".

A section change triggers three families of actions:
- recalc: compute derived values (CalcService)
- validate: run validation pipeline (no UI)
- refresh: update UI screens/widgets from the model

The orchestrator owns the mapping from action keys to callables.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Union

from app.sections import Section, Refresh


@dataclass(frozen=True)
class SectionSpec:
    # Use Enums to prevent typo-driven regressions.
    # The orchestrator uses Enums end-to-end (no .value).
    recalc: List[Section] = field(default_factory=list)
    validate: List[Section] = field(default_factory=list)
    refresh: List[Refresh] = field(default_factory=list)


# NOTE: action keys are implemented in SectionOrchestrator.
SECTION_GRAPH: Dict[Section, SectionSpec] = {
    # Base metadata changes can affect everything (voltages, utilization, etc.)
    Section.PROJECT: SectionSpec(
        recalc=[Section.CC],
        validate=[Section.PROJECT],
        refresh=[Refresh.MAIN, Refresh.CC, Refresh.BANK_CHARGER, Refresh.LOAD_TABLES, Refresh.DESIGNER],
    ),
    Section.INSTALACIONES: SectionSpec(
        recalc=[],
        validate=[Section.INSTALACIONES],
        refresh=[Refresh.INSTALACIONES, Refresh.CABINET, Refresh.BOARD_FEED, Refresh.CC, Refresh.DESIGNER],
    ),
    Section.CABINET: SectionSpec(
        recalc=[Section.CC],
        validate=[Section.CABINET],
        refresh=[Refresh.CABINET, Refresh.BOARD_FEED, Refresh.CC, Refresh.DESIGNER],
    ),
    Section.BOARD_FEED: SectionSpec(
        recalc=[],
        validate=[Section.BOARD_FEED],
        refresh=[Refresh.BOARD_FEED, Refresh.DESIGNER],
    ),
    Section.CC: SectionSpec(
        recalc=[Section.CC],
        validate=[Section.CC],
        refresh=[Refresh.CC, Refresh.LOAD_TABLES, Refresh.DESIGNER],
    ),
    Section.BANK_CHARGER: SectionSpec(
        recalc=[Section.BANK_CHARGER],
        validate=[Section.BANK_CHARGER],
        refresh=[Refresh.BANK_CHARGER, Refresh.LOAD_TABLES],
    ),
    Section.PROJECT_LOADED: SectionSpec(
        recalc=[Section.CC, Section.BANK_CHARGER],
        validate=[Section.PROJECT, Section.INSTALACIONES, Section.CABINET, Section.CC, Section.BANK_CHARGER],
        refresh=[Refresh.MAIN, Refresh.INSTALACIONES, Refresh.CABINET, Refresh.BOARD_FEED, Refresh.CC, Refresh.DESIGNER, Refresh.LOAD_TABLES],
    ),
}
