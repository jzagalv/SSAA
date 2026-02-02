# -*- coding: utf-8 -*-
"""Smoke test: cc_results extraction for UI display (PyQt-free)."""

from screens.cc_consumption.utils import extract_cc_totals_for_ui


def test_extract_cc_totals_for_ui():
    res = {"totals": {"p_total": 10.0, "i_total": 0.5}}
    out = extract_cc_totals_for_ui(res)
    assert out.get("p_total") == 10.0
    assert out.get("i_total") == 0.5
