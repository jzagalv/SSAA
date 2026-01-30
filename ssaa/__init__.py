"""SSAA Designer package entry.

This lightweight package provides a stable module entrypoint (python -m ssaa)
while keeping the existing top-level packages (app/, screens/, services/, etc.)
intact.
"""

from app.version import __version__  # single source of truth

__all__ = ["__version__"]
