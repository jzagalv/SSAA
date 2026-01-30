# -*- coding: utf-8 -*-
"""Section catalog (official ownership + guardrails).

This module is the *single source of truth* for:
- Which screen "owns" a given Section (i.e., is responsible for emitting changes)
- Which app attribute is expected to exist for each Refresh target

It provides light guardrails to avoid regressions when adding new screens/sections.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Optional

from app.sections import Section, Refresh

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class OwnerSpec:
    """Describes which screen owns a section or refresh target."""
    attr: str
    note: str = ""


# Official owners for *data sections*.
SECTION_OWNERS: Dict[Section, OwnerSpec] = {
    Section.PROJECT: OwnerSpec(attr="main_screen", note="Project metadata"),
    Section.INSTALACIONES: OwnerSpec(attr="location_screen", note="Ubicaciones/Instalaciones"),
    Section.CABINET: OwnerSpec(attr="cabinet_screen", note="Gabinetes y consumos por gabinete"),
    Section.CC: OwnerSpec(attr="cc_screen", note="Consumos CC"),
    Section.BANK_CHARGER: OwnerSpec(attr="bank_screen", note="Banco/Cargador"),
    Section.BOARD_FEED: OwnerSpec(attr="board_feed_screen", note="Alimentación tableros"),
    Section.DESIGNER: OwnerSpec(attr="ssaa_designer_screen", note="SSAA Designer"),
    Section.LOAD_TABLES: OwnerSpec(attr="load_tables_screen", note="Load Tables"),
}

# Official owners for *refresh targets*.
REFRESH_OWNERS: Dict[Refresh, OwnerSpec] = {
    Refresh.MAIN: OwnerSpec(attr="main_screen"),
    Refresh.INSTALACIONES: OwnerSpec(attr="location_screen"),
    Refresh.CABINET: OwnerSpec(attr="cabinet_screen"),
    Refresh.BOARD_FEED: OwnerSpec(attr="board_feed_screen"),
    Refresh.CC: OwnerSpec(attr="cc_screen"),
    Refresh.BANK_CHARGER: OwnerSpec(attr="bank_screen"),
    Refresh.DESIGNER: OwnerSpec(attr="ssaa_designer_screen"),
    Refresh.LOAD_TABLES: OwnerSpec(attr="load_tables_screen"),
}


def validate_catalog(app) -> None:
    """Validate that required screen attributes exist in *app*.

    This is a guardrail: it should not crash production, but it should make
    regressions obvious during development.
    """
    missing = []

    # Guardrail: prevent string keys from creeping back in.
    for k in SECTION_OWNERS.keys():
        if not isinstance(k, Section):
            msg = f"SECTION_OWNERS key must be Section, got {type(k).__name__}: {k!r}"
            if __debug__:
                raise TypeError(msg)
            log.warning(msg)
    for k in REFRESH_OWNERS.keys():
        if not isinstance(k, Refresh):
            msg = f"REFRESH_OWNERS key must be Refresh, got {type(k).__name__}: {k!r}"
            if __debug__:
                raise TypeError(msg)
            log.warning(msg)
    for sec, spec in SECTION_OWNERS.items():
        if not hasattr(app, spec.attr):
            missing.append(f"Section {sec.value}: missing app.{spec.attr}")
    for ref, spec in REFRESH_OWNERS.items():
        if not hasattr(app, spec.attr):
            missing.append(f"Refresh {ref.value}: missing app.{spec.attr}")
    if missing:
        msg = "Section catalog validation failed:\n- " + "\n- ".join(missing)
        # In debug, raise to surface regressions; in release, just log.
        if __debug__:
            raise AttributeError(msg)
        log.warning(msg)


def owner_for_section(section) -> Optional[str]:
    """Return app attribute name for the section owner (or None)."""
    try:
        sec = section if isinstance(section, Section) else Section(str(section))
    except Exception:
        return None
    spec = SECTION_OWNERS.get(sec)
    return spec.attr if spec else None
