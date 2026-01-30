# -*- coding: utf-8 -*-
"""ValidationService

Runs a set of pure validators and stores results in the DataModel.

- No PyQt dependency.
- Validators return core.types.Issue dataclass instances.
- The UI can render dm.proyecto['validation_issues'] (list of dicts).
"""

from __future__ import annotations

import logging
from typing import Dict, List

from app.sections import Section
from core.keys import ProjectKeys as K

from core.types import Issue, Severity

from core.validators.project import validate_project
from core.validators.instalaciones import validate_instalaciones
from core.validators.cabinet import validate_cabinet
from core.validators.cc import validate_cc
from core.validators.bank_charger import validate_bank_charger

log = logging.getLogger(__name__)


_VALIDATOR_MAP = {
    Section.PROJECT: validate_project,
    Section.INSTALACIONES: validate_instalaciones,
    Section.CABINET: validate_cabinet,
    Section.BOARD_FEED: lambda dm: [],
    Section.CC: validate_cc,
    Section.BANK_CHARGER: validate_bank_charger,
}


def _issue_to_dict(it: Issue) -> dict:
    sev = str(it.severity.value if hasattr(it.severity, "value") else it.severity)
    level = {
        "info": "info",
        "warning": "warn",
        "error": "error",
    }.get(sev, "warn")
    return {
        "code": it.code,
        "msg": it.message,
        "level": level,
        "context": it.context,
    }


class ValidationService:
    def __init__(self, data_model):
        self.dm = data_model

    def validate_sections(self, sections: List[Section]) -> Dict[str, List[dict]]:
        """Validate the given sections.

        Stores a flattened list under proyecto['validation_issues'].
        Also stores per-section lists in proyecto['validation_issues_by_section'].
        """
        dm = self.dm
        proyecto = getattr(dm, "proyecto", {}) or {}

        out_by_section: Dict[str, List[dict]] = {}  # keys are Section.value strings
        flat: List[dict] = []

        for sec in (sections or []):
            sec = sec if isinstance(sec, Section) else Section(str(sec))
            fn = _VALIDATOR_MAP.get(sec)
            if not fn:
                continue
            try:
                issues = fn(dm) or []
            except Exception:
                log.debug(f"validator {sec} failed", exc_info=True)
                issues = [Issue(code="VALIDATOR_CRASH", message=f"Validador '{sec}' falló (ver logs).", severity=Severity.WARNING, context=sec.value)]

            lst = [_issue_to_dict(it) for it in issues]
            out_by_section[sec.value] = lst
            flat.extend(lst)

        # Deduplicate by (code,msg,context)
        seen = set()
        uniq = []
        for it in flat:
            key = (it.get("code"), it.get("msg"), it.get("context"))
            if key in seen:
                continue
            seen.add(key)
            uniq.append(it)

        proyecto[K.VALIDATION_ISSUES_BY_SECTION] = out_by_section
        proyecto[K.VALIDATION_ISSUES] = uniq
        dm.proyecto = proyecto
        return out_by_section
