# Changelog
All notable changes to this project will be documented in this file.

The format is based on *Keep a Changelog* and this project adheres to *Semantic Versioning*.

## [1.4.0-alpha.161] - 2026-02-10
- Consumos C.C. (Permanentes): totales momentáneos unificados a `Ptotal - Ppermanente` con corriente derivada por `Vmin`.
- Consumos C.C. (Momentáneos): checkbox exclusivo por escenario para asignar la cola derivada de permanentes.
- UI: QComboBox en tablas con flecha nativa visible y menor recorte vertical de texto.
- Consumos (gabinetes): orden alfabético estable de la lista izquierda por texto visible.

## [1.4.0-alpha.160] - 2026-02-10
- Consumos C.C. (Permanentes): recálculo inmediato de totales desde modelo actual (sin quedar pegado a cache stale).
- Consumos C.C. (Permanentes): persistencia robusta de `% global`, `cc_usar_pct_global` y `% por fila` con autosave best-effort.
- UI tablas: autoajuste de columnas por texto más largo (headers + muestra de filas) para QTableView/QTableWidget.
- UI: QComboBox con flecha visible y ajuste compacto en tablas para evitar recorte de texto.

## [1.4.0-alpha.158] - 2026-02-09
- Fix: totales permanentes C.C. se actualizan al editar (refresco inmediato).
- Fix: lista gabinetes ordenada alfabéticamente por TAG de forma determinística.

## [1.4.0-alpha.157] - 2026-02-09
- Consumos (gabinetes): se corrige crash y se restablece copiar/pegar consumos (mapeo por TAG con lista ordenada).
- Consumos C.C.: se corrige crash al editar datos (restaurado iterador robusto de gabinetes en modelo).

## [1.4.0-alpha.156] - 2026-02-09
- Consumos (gabinetes): se corrige copiar/pegar consumos entre gabinetes (mapeo por TAG; lista ordenada ya no rompe la acción).

## [1.4.0-alpha.155] - 2026-02-09
- Librería de Consumos: filtros por búsqueda, tipo de consumo, alimentador y fase para facilitar lectura.

## [1.4.0-alpha.154] - 2026-02-09
- UI: QComboBox vuelve a mostrar flecha y se corrige recorte de texto en combos (incluye combos en tablas).

## [1.4.0-alpha.153] - 2026-02-09
- Consumos C.C.: auto-ajuste de ancho de columnas por contenido (texto más largo) en todas las tablas.
- Consumos C.C.: pulido final de layout/sorting/validaciones.

## [1.4.0-alpha.152] - 2026-02-09
- Consumos C.C.: persistencia de columnas por pestaña.
- Consumos C.C.: orden numérico real y formato uniforme.
- Consumos C.C.: validación/selector de escenarios en momentáneos.
- Consumos C.C.: export de imágenes más robusto.

## [1.4.0-alpha.151] - 2026-02-09
- Consumos (gabinetes): lista de gabinetes ordenada A–Z sin desincronizar selección.
- Consumos C.C.: corrección de textos (acentos, N°, guion largo y ellipsis).
- Consumos (gabinetes): deduplicación robusta de consumos por normalización de nombre.

## [1.4.0-alpha.150] - 2026-02-09
- Consumos (gabinetes): el marco del gabinete se recalcula y se ajusta al contenido (crece y encoge).
- Consumos (gabinetes): UI alineada con Instalaciones (margenes/spacing y paneles con groupbox).
- Consumos (gabinetes): restore del estado del header de la tabla.

## [1.4.0-alpha.149] - 2026-02-09
### Changed
- Proyecto: se agregó scroll para evitar corte de secciones y se ajustaron márgenes/espaciado.

## [1.4.0-alpha.148] - 2026-02-09
### Fixed
- Instalaciones: la sección Ubicaciones ya no se colapsa al cargar proyectos con gabinetes.

## [1.4.0-alpha.147] - 2026-02-09
### Changed
- Instalaciones: mejora visual con GroupBox, roles de botones y layout.
### Improved
- Instalaciones: botones Editar/Eliminar se habilitan solo con selección válida; tablas no editables por defecto (si aplica).

## [1.4.0-alpha.146] - 2026-02-09
### Fixed
- Instalaciones: operaciones de gabinetes ahora usan ID (compatible con ordenamiento de tabla) evitando editar/eliminar el registro incorrecto.

## [1.4.0-alpha.145] - 2026-02-09
### Changed
- Instalaciones: refactor a service+controller (UI desacoplada de lógica).
### Fixed
- Instalaciones: eliminado bug potencial por doble creación de tabla de gabinetes en initUI().

## [1.4.0-alpha.144] - 2026-02-08
### Fixed
- Modo moderno: corregido contraste (texto oscuro en UI clara) y desactivado fondo amarillo legacy en inputs.

## [1.4.0-alpha.143] - 2026-02-08
### Fixed
- En modo moderno, la sidebar ahora aplica estilo/seleccion correctamente al inicio (sin requerir cambio de pestana).

## [1.4.0-alpha.142] - 2026-02-08
### Changed
- Modern UI: estilo "glass claro" (A) para formularios/paneles y estilo tecnico (B) para tablas, activo solo en modo moderno.
### Unchanged
- Modo clasico sin cambios visuales.

## [1.4.0-alpha.141] - 2026-02-08
### Added
- Modern UI glass A/B system (forms vs tables), active only in modern mode.

## [1.4.0-alpha.139] - 2026-02-08
### Added
- Modo moderno con sidebar colapsable (navegacion lateral) sincronizado con tabs.
- Alternancia "Modo clasico / moderno" desde menu Ver -> Navegacion + persistencia en QSettings.
### Tech
- Estilos de sidebar integrados en `resources/styles.qss` usando tokens del theme.

## [1.4.0-alpha.138] - 2026-02-08
### Added
- Cuadros de carga C.A.: columnas completas segun template de planilla.
### Changed
- C.A. ahora se genera automaticamente para todos los tableros TD/TG con cargas en Arquitectura.
### Tech
- Motor `load_tables_engine` filtra tableros sin cargas alcanzables.

## [1.4.0-alpha.137] - 2026-02-08
### Fixed
- Alimentacion tableros: fila GENERAL ahora refleja solo consumos generales (derivados de components), evitando duplicidad cuando existen consumos individuales CA/CC.

## [1.4.0-alpha.136] - 2026-02-08
### Fixed
- Hotfix: Board Feed: restauradas funciones de inferencia a nivel módulo; corregida indentación y eliminado crash en load_data/showEvent.

## [1.4.0-alpha.135] - 2026-02-08
### Fixed
- Arquitectura SS/AA: lista "Tableros/Fuentes" ahora depende unicamente de TD/TG (is_board) definido en Instalaciones.
### Refactor
- Eliminado filtrado por prefijos TGxx/TDxx y flags CA/CC para tableros.

## [1.4.0-alpha.134] - 2026-02-08
### Fixed
- Arquitectura SS/AA: layout de puertos determinista y sin recomputes por selección.
- Fix: refactor layout de puertos y rutas independientes (constantes y helpers unificados).
### Changed
- Tableros: ancho por slots (X/Y/PADDING) y puertos equidistantes con persistencia.


## [1.4.0-alpha.133] - 2026-02-08
### Fixed
- Arquitectura SS/AA: rutas de aristas con lanes independientes y layout de puertos estable.
### Changed
- Selección de nodos ya no recalcula posiciones de puertos.

## [1.4.0-alpha.132] - 2026-02-08
### Fixed
- Arquitectura SS/AA: puertos manuales persistentes; layout determinista solo en cambios estructurales.
### Changed
- Tableros: desired_in/out ports en meta.ui y ancho ajustado sin borrar puertos extra.

## [1.4.0-alpha.131] - 2026-02-08
### Fixed
- Arquitectura SS/AA: layout estable de puertos; selección no recalcula; puertos equidistantes deterministas.
### Changed
- Tableros: ancho automático por cantidad de puertos IN/OUT con persistencia en meta.ui.

## [1.4.0-alpha.130] - 2026-02-08
### Fixed
- ssaa_designer: imports seguros y corrección de indentación en FeedListWidget.
### Added
- `tools/smoke_imports.py` para validar imports sin inicializar UI.

## [1.4.0-alpha.129] - 2026-02-08
### Fixed
- IndentationError en FeedListWidget (ssaa_designer/widgets).
### Added
- Script `scripts/check_syntax.py` para verificación de sintaxis con compileall.

## [1.4.0-alpha.128] - 2026-02-08
### Added
- Arquitectura SS/AA: etiquetas en conexiones con variables calculadas (placeholders listos para actualización).
- Arquitectura SS/AA: botón “Ordenar diagrama” para la capa actual.
### Changed
- Arquitectura SS/AA: tarjetas de ancho fijo con wrap + tooltip; tamaños persistidos en meta.ui.
- Tableros: puerto de entrada agregado y migración suave en carga.
- UI: “Alimentadores disponibles” renombrado a “Cargas disponibles”.
### Fixed
- Diagramas más estables al navegar entre capas (tamaños consistentes).

## [1.4.0-alpha.127] - 2026-02-08
### Added
- Alimentación tableros: botón “Asignación automática…” con vista previa y opción “solo inconsistencias”.
### Changed
- Reglas de asignación automática basadas en consumos reales por gabinete/componente.
### Fixed
- Alimentación tableros: aplicación de cambios sin refresco total ni pérdida de scroll.

## [1.4.0-alpha.126] - 2026-02-06
### Added
- Toggle “Balance automático por fases (usa VA)” en cuadros de carga CA.
### Changed
- Motor de cuadros de carga CA usa fp/fd del usuario para VA y corrientes.
- Balanceo automático por fases en CA respeta fase manual si existe.
### Fixed
- Corrientes CA calculadas desde VA (no W) para consistencia con ingeniería.

## [1.4.0-alpha.125] - 2026-02-03
### Changed
- Alimentación tableros: validaciones basadas en consumos reales (CC/CA esencial/no esencial) y menor ruido.
### Fixed
- Versionado unificado: `app/version.py` lee desde `version.json` (SSOT).

## [1.4.0-alpha.124] - 2026-02-03
### Fixed
- Board Feed: marcar/desmarcar checkboxes ya no resetea el scroll de la tabla; se evita el refresh circular.

## [1.4.0-alpha.123] - 2026-02-03
### Changed
- Se eliminan acciones masivas de asignación en Alimentación tableros; se vuelve a asignación directa por checkbox.

## [1.4.0-alpha.122] - 2026-02-03
### Added
- Arquitectura SS/AA: panel de “Tableros/Fuentes disponibles” desde Alimentación tableros (no consumible, root sin entrada).
### Changed
- Alimentación tableros: contador de inconsistencias en el botón y acciones masivas de marcado/limpieza.
- Issues: validaciones con menos ruido (FEED_SELECTED_NOT_USED agrupado/“info”, reglas más relevantes).
### Fixed
- Sincronización automática entre Consumos (gabinetes) ↔ Alimentación tableros ↔ Arquitectura SS/AA (debounced refresh).

## [1.4.0-alpha.121] - 2026-02-03
### Added
- Panel “Fuentes disponibles” en Arquitectura SS/AA (global, no consumible).
### Changed
- Validaciones/Issues ajustadas: fuentes inválidas, fuentes sin uso global y warning de alimentadores agrupado.

## [1.4.0-alpha.120] - 2026-02-03
### Fixed
- Loop infinito de logging ante excepciones no controladas.
- Edición segura de tablas: refresh diferido y sin re-entrancia (evita QTableWidgetItem destruido).

## [1.4.0-alpha.119] - 2026-02-02
### Fixed
- Fix(UI): resaltado amarillo de celdas editables en tablas (delegate compatible con QSS), incluye Comprobación N° celdas en Manual.

## [1.4.0-alpha.118] - 2026-02-02
### Fixed
- Fix: estandarización UTF-8 en I/O y corrección de textos con tildes al cargar proyectos/librerías.

## [1.4.0-alpha.117] - 2026-02-02
### Fixed
- Fix(UI): fondo amarillo en “Número de celdas” (Comprobación) cuando modo Manual.

## [1.4.0-alpha.116] - 2026-02-02
### Fixed
- Fix(UI): 2 decimales en tensión máxima.
- UX: combo Vpc Auto no se ve gris; Manual se ve amarillo.

## [1.4.0-alpha.115] - 2026-02-02
### Fixed
- Fix(UI): eliminado auto_resize legacy y estandarizado auto-fit debounced en todas las tablas.
- Perf: reducción de tiempos de refresh en tablas grandes (especialmente CC).

## [1.4.0-alpha.113] - 2026-02-02
### Fixed
- UI: autoajuste de columnas optimizado (debounce) para evitar lentitud severa en tablas grandes (CC).

## [1.4.0-alpha.112] - 2026-02-02
### Changed
- UI: auto-fit real de columnas por contenido más extenso en todas las tablas; resize manual habilitado.

## [1.4.0-alpha.110] - 2026-02-02
### Fixed
- Banco y cargador: formato a 2 decimales y modos Auto/Manual para Vpc final y número de celdas, con validaciones.

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
