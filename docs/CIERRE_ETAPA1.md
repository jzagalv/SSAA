# Cierre de Etapa 1

Esta guía define cuándo la Etapa 1 se puede dar por cerrada, y qué checklist ejecutar antes de continuar escalando.

## 1) Contratos de arquitectura (reglas)

### DataModel
- No importa PyQt.
- Es la **fuente única de verdad** del proyecto.
- Emite eventos (observer) para desacoplar pantallas.

### Servicios
- No importan pantallas.
- `CalcService` orquesta cálculos y guarda resultados en `runtime_cache`.
- `ValidationService` genera issues sin UI.
- `SectionOrchestrator` ejecuta el grafo declarativo `SECTION_GRAPH`.

### Pantallas (Screens)
- `__init__` solo arma UI y deja el estado “seguro” (sin recalc/refresh pesado).
- Los refresh/cálculos ocurren por orquestador (post-load o cambios de datos).
- Cambios de pestaña usan `DataModel.notify_section_viewed()` (refresh-only, sin recalc).

## 2) Checklist de cierre

### Funcional
- [ ] Arranque en frío (sin proyecto cargado) no arroja errores.
- [ ] Abrir un `.ssaa` (ej: Don Melchor) carga datos y pantallas coherentes.
- [ ] Guardar, Guardar como…, reabrir: no se pierde info.
- [ ] Validaciones (issues) se muestran y no rompen el flujo.

### UX/Performance (mínimo)
- [ ] Al abrir proyecto se muestra feedback inmediato (“Cargando…” / “Actualizando pantallas…”).
- [ ] Cambiar entre pantallas no dispara recálculo (solo refresh); sin "lag" evitable.

### Robustez
- [ ] No hay imports rotos (Pylance sin `reportMissingImports`).
- [ ] `pytest` (si aplica) corre sin fallas.

### Versionado
- [ ] `app/version.py` y `version.json` sincronizados.
- [ ] `CHANGELOG.md` actualizado con lo hecho en esta versión.

## 3) Qué queda para la Etapa 2 (no bloqueante)

- Paralelizar carga pesada (thread) manteniendo UI responsive.
- Empaquetado/instalador final (PyInstaller + Inno Setup) con recursos, libs y licencia.
- Política de licencias y “kill switch” (si aplica) con auditoría/telemetría opcional.
