# -*- coding: utf-8 -*-
"""Coalescing helper tests (PyQt-free)."""

from services.compute.orchestrator_core import is_stale_result


def test_is_stale_result():
    assert is_stale_result(5, 4) is True
    assert is_stale_result(5, 5) is False
