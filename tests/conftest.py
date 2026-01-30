# -*- coding: utf-8 -*-

"""Pytest configuration.

This project is a simple app folder layout (not installed as a package).
For local testing we add the repository root to sys.path so that imports like
`from core...` work reliably.
"""

from __future__ import annotations

import os
import sys


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
