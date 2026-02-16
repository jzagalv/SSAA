# -*- coding: utf-8 -*-
from __future__ import annotations

from app.dirty_tracker import DirtyTracker


def test_dirty_tracker_marks_and_clears() -> None:
    tracker = DirtyTracker()
    assert tracker.is_dirty is False

    tracker.mark_dirty(reason="user_edit", keys={"tension_nominal"})
    assert tracker.is_dirty is True
    assert "user_edit" in tracker.last_change_summary

    tracker.clear_dirty()
    assert tracker.is_dirty is False
    assert tracker.last_change_summary == ""


def test_dirty_tracker_suspend_context() -> None:
    tracker = DirtyTracker()
    assert tracker.is_dirty is False

    with tracker.suspend_tracking():
        tracker.mark_dirty(reason="ignored")
        assert tracker.is_dirty is False

    tracker.mark_dirty(reason="applied")
    assert tracker.is_dirty is True


def test_dirty_tracker_sync_respects_suspend_unless_forced() -> None:
    tracker = DirtyTracker()
    tracker.suspend()
    try:
        tracker.sync_from_model(True)
        assert tracker.is_dirty is False

        tracker.sync_from_model(True, force=True)
        assert tracker.is_dirty is True
    finally:
        tracker.resume()
