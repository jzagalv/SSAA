# -*- coding: utf-8 -*-
"""Regression: placeholder must not wipe saved scenario names."""
from __future__ import annotations

from screens.cc_consumption.utils import persist_desc_if_real


def test_placeholder_does_not_wipe_saved_name():
    existing = {"1": "87B"}
    out = persist_desc_if_real(existing.copy(), 1, "Escenario 1")
    assert out.get("1") == "87B"


def test_real_text_updates_name():
    existing = {"1": "87B"}
    out = persist_desc_if_real(existing.copy(), 1, "Nuevo")
    assert out.get("1") == "Nuevo"
