# -*- coding: utf-8 -*-
"""Background worker for CC compute (Qt)."""
from __future__ import annotations

from typing import Any, Dict
import traceback

try:
    from PyQt5.QtCore import QObject, QRunnable, pyqtSignal
except Exception:  # pragma: no cover - optional for test environments
    QObject = None
    QRunnable = object
    pyqtSignal = None

from services.compute.cc_compute_service import CCComputeService


if QObject is not None:

    class _WorkerSignals(QObject):
        finished = pyqtSignal(int, dict)
        error = pyqtSignal(int, object)


    class CCComputeWorker(QRunnable):
        def __init__(self, project_snapshot: Dict[str, Any], compute_id: int) -> None:
            super().__init__()
            self._snapshot = project_snapshot
            self._compute_id = int(compute_id)
            self.signals = _WorkerSignals()

        def run(self) -> None:
            try:
                results = CCComputeService().compute(self._snapshot)
                self.signals.finished.emit(self._compute_id, results)
            except Exception as exc:
                tb = traceback.format_exc()
                self.signals.error.emit(self._compute_id, (exc, tb))

else:

    class CCComputeWorker:  # pragma: no cover
        def __init__(self, *args, **kwargs) -> None:
            raise RuntimeError("PyQt5 is required to use CCComputeWorker")
