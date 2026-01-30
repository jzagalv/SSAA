# -*- coding: utf-8 -*-
"""
Application bootstrap (runs before UI):
- Init logging
- Ensure base libraries are seeded to user space
"""
from __future__ import annotations

from infra.logging_setup import init_logging, init_license_logging, init_perf_logging
from infra.perf import is_enabled as perf_enabled
from infra.settings import ensure_seed_libs
from infra.migrations import migrate_if_needed

def bootstrap() -> None:
    init_logging()
    init_license_logging()
    if perf_enabled():
        init_perf_logging()
    ensure_seed_libs()
    migrate_if_needed()
