# -*- coding: utf-8 -*-
"""Pure helpers for CC Consumption screens."""
from __future__ import annotations


def is_placeholder(n: int, text: str | None) -> bool:
    t = (text or "").strip()
    return t == f"Escenario {int(n)}"


def resolve_scenario_desc(n: int, prev: str | None, db: str | None) -> str:
    placeholder = f"Escenario {int(n)}"
    p = (prev or "").strip()
    d = (db or "").strip()

    if not p:
        return d or placeholder
    if p == placeholder and d and d != placeholder:
        return d
    return p or d or placeholder


def persist_desc_if_real(existing: dict, n: int, ui_text: str) -> dict:
    """Persist UI text only when it is a real (non-placeholder) name."""
    if not isinstance(existing, dict):
        existing = {}
    text = (ui_text or "").strip()
    if not text or is_placeholder(n, text):
        return existing
    existing[str(n)] = text
    return existing


def should_persist_scenario_desc(n: int, text: str | None) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    if is_placeholder(n, t):
        return False
    return True


def extract_cc_totals_for_ui(results: dict | None) -> dict:
    """Extract totals for UI rendering from cc_results (pure helper)."""
    if not isinstance(results, dict):
        return {}
    totals = results.get("totals")
    return totals if isinstance(totals, dict) else {}


def fmt(value: object, default: float = 0.0) -> str:
    """Uniform numeric formatting for CC UI tables/totals."""
    try:
        if value is None:
            num = float(default)
        elif isinstance(value, (int, float)):
            num = float(value)
        else:
            num = float(str(value).strip().replace(",", "."))
    except Exception:
        num = float(default)
    return f"{num:.2f}"
