# -*- coding: utf-8 -*-
"""services/errors.py

Tipos compartidos para reportar problemas a la UI (sin depender de PyQt).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Level(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass(frozen=True)
class Issue:
    level: Level
    code: str
    message: str
    field: Optional[str] = None
    hint: Optional[str] = None
