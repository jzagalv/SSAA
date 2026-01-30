# -*- coding: utf-8 -*-
"""Backwards-compatible import path for section keys.

Prefer importing from :mod:`core.sections`.
This module re-exports Section/Refresh to avoid breaking existing imports.
"""

from __future__ import annotations

from core.sections import Section, Refresh  # re-export
