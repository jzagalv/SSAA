# -*- coding: utf-8 -*-
"""Shared domain types (pure, test-friendly)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class Issue:
    code: str
    message: str
    severity: Severity = Severity.WARNING
    context: Optional[str] = None
