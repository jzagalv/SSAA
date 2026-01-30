# Changelog
All notable changes to this project will be documented in this file.

The format is based on *Keep a Changelog* and this project adheres to *Semantic Versioning*.

## [Unreleased]

## [1.4.0-alpha.68] - 2026-01-02
### Fixed
- Consumos C.C. → Momentáneos: el resumen por escenario ahora suma según 'Incluir' y el escenario seleccionado (cc_mom_incluir/cc_mom_escenario) y actualiza al cargar.
- Consumos C.C. → Momentáneos: descripción del escenario se recupera también desde formatos legacy (cc_scenarios_summary) cuando cc_escenarios no existe.

## [1.4.0-alpha.67] - 2026-01-02
### Fixed
- Consumos C.C. Momentáneos: restore scenario combobox and persisted flags (incluir/escenario).
- Fix crash when adding scenarios (missing CCConsumptionController.set_project_value).
- Ensure scenario summary table is built on project load (scenario 1 visible).


## [1.4.0-alpha.64] - 2026-01-02
### Fixed
- CC Consumption: corregido KeyError 'p_total' al entrar a Permanentes; compute_totals ahora siempre entrega p_total/i_total y la UI hace fallback seguro.


## [1.4.0-alpha.63] - 2026-01-01
### Changed
- Versión “lite”: CI mínimo (pytest + architecture check), removido pre-commit y checks de ruff por defecto.
- Mantiene documentación y smoke tests de proyectos .ssaa.

## [1.4.0-alpha.62] - 2026-01-01
### Added
- GitHub Actions CI workflow (lint/format/tests + architecture boundaries).
- Windows PyInstaller build workflow (manual + tag builds).
- Ruff configuration (lint + formatter) and dev dependencies.
- Pre-commit hooks for ruff, formatting, architecture checks, and pytest (pre-push).

### Changed
- Fixed invalid `pyproject.toml` placeholder content and aligned metadata/version.


## [1.4.0-alpha.61] - 2026-01-01
### Added
- `docs/ARCHITECTURE.md` con capas, reglas de imports y patrón Screen/Controller/Service/Facade.
- `docs/PYINSTALLER_WINDOWS.md` + receta PyInstaller (`build/pyinstaller/SSAA.spec`) y script `scripts/build_pyinstaller.ps1`.
- `scripts/check_architecture.py` para verificar automáticamente límites de capas (domain/services/storage).

### Changed
- Versionado actualizado a `1.4.0-alpha.61` (single source of truth en `app/version.py`).



## [1.4.0-alpha.60] - 2026-01-01
### Added
- Added two additional sample .ssaa projects for smoke testing (modern + edge cases).
- Parametrized smoke test to run upgrade/normalization across all sample projects.

## [1.4.0-alpha.59] - 2026-01-01
### Added
- `tests/data/sample_project.ssaa`: proyecto de ejemplo (legacy) para validar migraciones.
- Smoke test PyQt-free que carga el proyecto de ejemplo, ejecuta `upgrade_project_dict` y valida normalización.
## [1.4.0-alpha.58] - 2026-01-01
### Added
- PyQt-free unit tests for `domain/ProjectFacade` (topology layers + CC scenario helpers).
- PyQt-free unit tests for `storage/migrations.upgrade_project_dict()` ensuring idempotency and stable defaults.
- Smoke test for JSON roundtrip (serialize -> load -> upgrade) using a minimal project dict.


## [1.4.0-alpha.57] - 2026-01-01
### Added
- `ProjectKeys.SSAA_TOPOLOGY_LAYERS` and `ProjectKeys.VALIDATION_ISSUES` for designer-related persisted keys.
- `ProjectFacade` helpers for SSAA designer topology layers and validation issues.

### Changed
- SSAA Designer persistence now reads/writes topology exclusively via `ProjectFacade` (best-effort migration from legacy `SSAA_TOPOLOGY`).
- Load Tables engine reads topology using `ProjectKeys.SSAA_TOPOLOGY_LAYERS` (no raw string key).

### Fixed
- SSAA Designer controller reads `validation_issues` using `ProjectFacade` (avoids raw-key drift).

## [1.4.0-alpha.56] - 2026-01-01
### Added
- Entrada de módulo `python -m ssaa` y script de consola `ssaa` (pyproject.toml).

### Changed
- Eliminado el ajuste dinámico de `sys.path` en `main.py` (se favorece ejecución como módulo/paquete).

## [1.4.0-alpha.55] - 2026-01-01
### Added
- `app/base_controller.py` providing consistent `mark_dirty()`, `notify_changed()`, and `safe_call()` (no Qt dependency).

### Changed
- CC Consumption controller now inherits `BaseController` for uniform dirty/notify behavior.
- Bank Charger controller adopts `BaseController.safe_call()` for best-effort edit commits and persistence calls.

### Fixed
- SSAA Designer controller: `refresh_issues_panel()` is now a proper class method (was accidentally a top-level function) and global validations are executed via `safe_call()`.


## [1.4.0-alpha.54] - 2026-01-01
### Added
- `screens/cc_consumption/widgets.py` with table column indices/headers, table factory helpers, and UI render helpers.

### Changed
- `cc_consumption_screen.py` now imports table columns/factories from `widgets.py` and delegates table population to render helpers, reducing screen size and improving maintainability.
- Table creation in CC Consumption now uses shared factory helpers for consistent configuration.

## [1.4.0-alpha.53] - 2026-01-01
### Added
- `CHANGELOG.md` following Keep a Changelog.
- `core/keys.py` as a single source of truth for persisted project keys.
- `domain/project_facade.py` to encapsulate project dict access (defaults + typed-ish getters/setters).
- Global crash/exception handler hook (`infra/crash_handler.py`) to ensure unexpected errors are logged.

### Changed
- Version is now a single source of truth from `app/version.py` (root `__init__.py` re-exports it).
- SSAA Designer persistence now uses `ProjectKeys`/`ProjectFacade` for topology storage.
- CC Consumption controller consolidates scenario editing and keeps `cc_escenarios` + legacy `cc_scenarios_summary` in sync.

### Fixed
- Removed duplicated/contradictory `PROJECT_EXT` definition (one source of truth in `storage/project_paths.py`).
- Fixed `ProjectFacade.set_cc_scenarios()` bug where it accidentally overwrote scenarios with a list.

## [1.4.0-alpha.52] - 2025-??-??
### Notes
- Prior release baseline (from `version.json`).
