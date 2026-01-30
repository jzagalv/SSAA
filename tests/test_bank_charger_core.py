# -*- coding: utf-8 -*-
from core.calculations.bank_charger import compute_bank_charger


def test_bank_charger_returns_summary_keys():
    proyecto = {"ieee485_kt": {}}
    bundle, summary = compute_bank_charger(proyecto=proyecto, periods=[], rnd=None, i_perm=0.0)
    assert isinstance(summary, dict)
    assert "missing_kt_keys" in summary
    assert "bank" in summary
    assert "charger" in summary
