# -*- coding: utf-8 -*-
from core.models.cc import CCLoadRow
from core.calculations.cc import compute_cc_summary


def test_cc_summary_empty():
    s = compute_cc_summary([], vmin=110.0)
    assert s.p_total_w == 0.0
    assert s.i_perm_a == 0.0


def test_cc_summary_basic():
    rows = [
        CCLoadRow(tag="A", description="a", power_w=100.0, pct_util=50.0),
        CCLoadRow(tag="B", description="b", power_w=100.0, pct_util=100.0),
    ]
    s = compute_cc_summary(rows, vmin=100.0)
    assert round(s.p_total_w, 3) == 200.0
    assert round(s.p_perm_w, 3) == 150.0
    assert round(s.p_mom_w, 3) == 50.0
    assert round(s.i_perm_a, 3) == 1.5
