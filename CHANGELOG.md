# Changelog
All notable changes to this project will be documented in this file.

The format is based on *Keep a Changelog* and this project adheres to *Semantic Versioning*.

## [1.4.0-alpha.109] - 2026-02-02
### Fixed
- CC Momentáneos: el resumen por escenarios ya no queda desactualizado al cargar proyectos; se valida/invalida cache con firma del estado y se recalcula automáticamente.

## [1.4.0-alpha.108] - 2026-02-02
### Fixed
- Perf: Banco y cargador ahora refresca por sub-tab (lazy refresh); elimina freeze de ~3.5s al entrar a "Datos y comprobación".

## [1.4.0-alpha.107] - 2026-02-02
### Fixed
- Banco y cargador: refresh ya no ejecuta recálculo completo (evita freeze ~3s); se muestran derivados livianos al cargar.

## [1.4.0-alpha.106] - 2026-02-02
### Added
- Selector de tema Claro/Oscuro en menÃº Ver > Tema con cambio en caliente y persistencia.
### Changed
- MigraciÃ³n de colores de UI a tokens/QSS donde corresponde (base mantiene colores actuales).

## [1.4.0-alpha.102] - 2026-02-01
### Fixed
- CC: totales de Permanentes ya no dependen de cc_results; se calculan desde calculated.cc/controller.
- CC: resumen de Momentáneos muestra p/i por escenario correctamente.
- CC: Aleatorios: checkbox Sel. persiste y refleja estado (agregado get_random_selected) y totales seleccionados correctos.

## [1.4.0-alpha.105] - 2026-02-01
### Fixed
- CC Aleatorios: totales seleccionados ahora se calculan en vivo con compute_random (sin depender de calculated.cc.summary).
- CC Aleatorios: labels de totales se actualizan al marcar/desmarcar "Sel." (dataChanged conectado).

## [1.4.0-alpha.104] - 2026-02-01
### Fixed
- CC Momentáneos: el resumen por escenarios ya no queda congelado en ceros cuando calculated.cc.scenarios_totals está stale; se recalcula al editar Incluir/Escenario.
- CC Momentáneos: el momentáneo derivado desde permanentes vuelve a sumarse al escenario 1.

## [Unreleased]
### Fixed
- Tests/CI no requieren PyQt para importar CC table schema.
- Aleatorios now displays correct I values.
- Scenario name persistence no longer depends on UI commits; placeholders never overwrite saved names.
- CC now recalculates only via orchestrator; UI renders from cc_results.
- Removed legacy UI recalc paths and duplicate timers.
- Crash on startup when wiring global utilization spinbox (missing handler).
- cc_results treated as derived and excluded from persistence.
- NameError fix: logging imported in app/controller.py.
- Faster project save (removed derived componentes.gabinetes duplication).
- Tests are UTF-8 clean and CI-safe.
- cc_consumption package no longer imports UI in __init__.py (import-safe utilities).
- Tests are UTF-8 clean; cc_consumption utils import no longer pulls PyQt5 via __init__.
- Tests ahora UTF-8 clean; cc_consumption utils desacoplado de imports PyQt.
- Placeholder "Escenario N" ya no borra nombres reales guardados en cc_escenarios durante commits/refresh.
- Momentaneos ya no muestra placeholders cuando hay nombre real guardado.
- cc_scenarios_summary default ahora es lista (no dict).
- Declared missing runtime deps (matplotlib, PyJWT, cryptography) and added startup dependency checks.
- Renamed .gitignoge to .gitignore.
- Consumos C.C. ahora refleja cargas de gabinetes (SSOT gabinetes + sync entre instalaciones["gabinetes"] y data_model.gabinetes).
- Refresco confiable al cambiar de pestaña y al editar valores (refresh debounced via orchestrator).
- Crash en Consumos C.C. por loader faltante load_permanentes.
- Rutas de librerías ahora son relativas y con fallback si faltan archivos.
- Crash en totales de permanentes cuando no existe summary calculado.
- Selección de aleatorios ahora persiste y se recarga correctamente.
- Totales aleatorios se actualizan en tiempo real al marcar/desmarcar.
- Persistencia de aleatorios y momentÃ¡neos ahora hace roundtrip (flags por componente).
- Nombres de escenarios en C.C. Momentáneos ahora persisten (metadata sin refresh/recalc).
- Contrato CC unificado en proyecto.cc_escenarios (sin schema paralelo).
- Migración CC integrada en upgrade_project_dict (una sola pipeline).
- Restaurado pipeline único de migración (sin migrate_to_v3).
- SSOT: identidad de listas gabinetes/ubicaciones garantizada (sin copias).
- DataModel.project root definido para tracking de librerías.
- Project load ahora popula vistas legacy aun con project_model (roundtrip estable).

### Added
- Tests de journeys CC (persistencia y no-mezcla).
- Automatic CC recalculation on input changes (debounced).
- Regression tests for CC auto-recalc debounce and no-loop.
- CC background compute with coalescing and cancellation.

### Improved
- Migrated CC Momentaneos loads table to QAbstractTableModel (MVC, faster refresh).
- Migrated CC Momentaneos scenarios summary to QAbstractTableModel.
- CC UI refresh now driven by Computed(CC); no manual recalculation needed.
- UI remains responsive during heavy CC computations.
- Migrated CC Permanentes table to QAbstractTableModel (MVC, faster refresh, easier maintenance).
- Migrated CC Aleatorios table to QAbstractTableModel (better performance and maintainability).
- Coalesced CC refresh events to avoid double refresh.
- Perf logging for save serialization (time + size).
- No se persisten placeholders "Escenario N" en cc_escenarios.
- EventBus ahora registra errores de handlers (debug).

### Chore
- Cleanup legacy CC table code and consolidate utilities (no functional changes).
- Remove unused imports/comments; improve test import-safety.
- Remove python cache artifacts and harden gitignore.
- Improve compute error logging and remove runtime prints.
- Fix orchestrator docstrings for background compute.

### Refactor
- Se separa cc_scenarios_summary (legacy nombres) de escenarios_totals (calculated.cc).
- Contrato JSON v3 para CC (migración + normalización en carga).
- SSOT gabinetes canonical en instalaciones.gabinetes (se evitan duplicados persistidos).
- Runtime SSOT con Project/Cabinet/Component y serializer dedicado (sin duplicar gabinetes/componentes).
- Refresh orientado a eventos (metadata/input/model) con debounce para CC.
- Helpers de esquema de tablas C.C. centralizados (lectura/escritura por fila).

### Fixed
- CC no reconstruye al editar nombres de escenario (evita pisar metadata).

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
- Tests de journeys CC (persistencia y no-mezcla).
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
