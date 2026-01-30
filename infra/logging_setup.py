# -*- coding: utf-8 -*-
"""
Logging setup confirms crashes/tracebacks are captured in user space.
"""
from __future__ import annotations

import logging
from pathlib import Path

from infra.paths import logs_dir

def init_logging(filename: str = "app.log") -> Path:
    log_path = logs_dir() / filename
    # Don't add multiple handlers if init called twice
    root = logging.getLogger()
    if not any(isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", "") == str(log_path) for h in root.handlers):
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
            handlers=[logging.FileHandler(log_path, encoding="utf-8"), logging.StreamHandler()],
        )
    return log_path


def init_license_logging(filename: str = "license.log") -> Path:
    """Attach a dedicated file handler for license-related logs.

    This keeps license/activation troubleshooting separate from the main app log.
    """
    log_path = logs_dir() / filename
    logger = logging.getLogger("services.license_service")
    logger.setLevel(logging.INFO)
    # Avoid duplicate handlers
    if not any(isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", "") == str(log_path) for h in logger.handlers):
        fh = logging.FileHandler(log_path, encoding="utf-8")
        fh.setLevel(logging.INFO)
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logger.addHandler(fh)
    return log_path


def init_perf_logging(filename: str = "perf.log") -> Path:
    """Attach a dedicated file handler for performance timings.

    Timings are emitted by infra.perf.span when SSAA_PERF=1.
    """
    log_path = logs_dir() / filename
    logger = logging.getLogger("ssaa.perf")
    logger.setLevel(logging.INFO)
    # Avoid duplicate handlers
    if not any(isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", "") == str(log_path) for h in logger.handlers):
        fh = logging.FileHandler(log_path, encoding="utf-8")
        fh.setLevel(logging.INFO)
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logger.addHandler(fh)
    return log_path
