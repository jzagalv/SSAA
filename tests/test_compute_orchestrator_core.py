# -*- coding: utf-8 -*-
"""Tests for the compute orchestrator core (PyQt-free)."""

from services.compute.orchestrator_core import ComputeOrchestratorCore
from app.sections import Section


def test_debounce_and_coalesce():
    core = ComputeOrchestratorCore(debounce_ms=200)
    core.mark_dirty(Section.CC, now=0.0)
    core.mark_dirty(Section.CC, now=0.05)
    assert core.should_run(now=0.1) is False
    assert core.should_run(now=0.3) is True
    dirty = core.pop_dirty()
    assert Section.CC in dirty
    assert core.has_dirty() is False


def test_mark_again_after_pop():
    core = ComputeOrchestratorCore(debounce_ms=100)
    core.mark_dirty(Section.CC, now=1.0)
    assert core.should_run(now=1.2) is True
    core.pop_dirty()
    core.mark_dirty(Section.CC, now=2.0)
    assert core.should_run(now=2.05) is False
