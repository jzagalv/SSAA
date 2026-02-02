# -*- coding: utf-8 -*-
"""SSAA Designer entrypoint.

Intentionally minimal:
- bootstrap (paths, logging, etc.)
- QApplication creation
- apply global style
- show main window
- optional license gate (cloud mode)
"""
import sys

try:
    from PyQt5.QtWidgets import QMessageBox
except Exception:  # pragma: no cover - optional dependency pre-check
    QMessageBox = None


def main() -> None:
    from app.deps import ensure_runtime_deps

    try:
        ensure_runtime_deps()
    except RuntimeError as exc:
        message = str(exc)
        if QMessageBox is not None:
            try:
                from PyQt5.QtWidgets import QApplication

                app = QApplication.instance()
                if app is None:
                    app = QApplication([])
                QMessageBox.critical(None, "SSAA - Dependencias faltantes", message)
            except Exception:
                print(message, file=sys.stderr)
        else:
            print(message, file=sys.stderr)
        sys.exit(1)

    from PyQt5.QtWidgets import QApplication, QMessageBox

    from app.bootstrap import bootstrap
    from app.controller import create_main_window
    from infra.crash_handler import install_global_exception_handlers
    from infra.settings import repair_user_space
    from services.license_service import check_license, wipe_local_license_files
    from ui.recovery_dialog import LicenseRecoveryDialog
    from ui.common.state import get_ui_theme
    from ui.theme import apply_named_theme

    bootstrap()
    # Ensure unexpected exceptions are captured in logs
    install_global_exception_handlers()

    app = QApplication(sys.argv)

    # Installer shortcuts / maintenance commands
    args = set(sys.argv[1:])
    if "--repair" in args:
        # Best-effort repair of per-user data and license state
        repair_user_space()
        wipe_local_license_files()
        QMessageBox.information(None, "SSAA - Reparación", "Reparación completada.\n\nSi tu versión usa licencia (modo cloud), usa 'Revalidar licencia' con internet para regenerar el estado.")
        return

    if "--revalidate" in args:
        st = check_license(force_online=True)
        if st.ok:
            QMessageBox.information(None, "SSAA - Licencia", "Licencia validada correctamente.")
        else:
            QMessageBox.critical(None, "SSAA - Licencia", f"No se pudo validar la licencia en línea.\n\nDetalle: {st.reason}")
        return

    # Apply theme/QSS (safe no-op if missing)
    try:
        apply_named_theme(app, get_ui_theme())
    except Exception:
        # Don't block startup if theme fails; log is handled by bootstrap.
        pass

    st = check_license()
    if not st.ok:
        dlg = LicenseRecoveryDialog(reason=str(st.reason))
        if dlg.exec_() != dlg.Accepted:
            return

    window = create_main_window()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
