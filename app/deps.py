# -*- coding: utf-8 -*-
"""Runtime dependency checks for SSAA."""
from __future__ import annotations

from importlib import import_module


def missing_runtime_packages() -> list[str]:
    """Return a list of missing runtime package names (pip names)."""
    missing: list[str] = []
    checks = [
        ("PyQt5", "PyQt5"),
        ("PyJWT", "jwt"),
        ("matplotlib", "matplotlib"),
        ("cryptography", "cryptography"),
    ]
    for package_name, import_name in checks:
        try:
            import_module(import_name)
        except ModuleNotFoundError:
            missing.append(package_name)
    return missing


def ensure_runtime_deps() -> None:
    """Raise RuntimeError with install guidance if required deps are missing."""
    missing = missing_runtime_packages()
    if not missing:
        return
    joined = ", ".join(missing)
    message = (
        "Missing required Python packages: "
        f"{joined}.\n\n"
        "Install them with one of the following commands:\n"
        "  pip install -r requirements.txt\n"
        "  pip install -e ."
    )
    raise RuntimeError(message)
