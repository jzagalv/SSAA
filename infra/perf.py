# -*- coding: utf-8 -*-
"""Lightweight performance instrumentation.

We use this to understand and eliminate UI lag without shipping a full profiler.

Enable by setting env var:
    SSAA_PERF=1

When enabled, timings are written to logger ``ssaa.perf``.

Design constraints
------------------
- Best-effort: must never crash the UI.
- No third-party dependencies.
- Works in source runs and packaged builds.
"""

from __future__ import annotations

import logging
import os
import time
from contextlib import contextmanager

_perf_env = os.environ.get("SSAA_PERF", "").strip().lower()
ENABLED = _perf_env in ("1", "true", "yes", "on")

log = logging.getLogger("ssaa.perf")


def is_enabled() -> bool:
    return ENABLED


@contextmanager
def span(label: str, *, threshold_ms: float = 50.0):
    """Measure a block duration and log if above threshold.

    If SSAA_PERF is not enabled, this context manager is basically a no-op.
    """
    if not ENABLED:
        yield
        return
    t0 = time.perf_counter()
    try:
        yield
    finally:
        dt_ms = (time.perf_counter() - t0) * 1000.0
        if dt_ms >= float(threshold_ms or 0.0):
            log.info("PERF %s %.1fms", label, dt_ms)
