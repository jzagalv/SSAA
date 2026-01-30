# SSAA — Arranque y Contratos (UI/DataModel)

Este documento define **las reglas del juego** para que el proyecto escale sin “parches” que luego explotan.

## Política de arranque (Startup Policy)

En `__init__` de pantallas y ventana principal:

- ✅ **Permitido**
  - Construir widgets (UI)
  - Conectar señales
  - Inicializar tablas/listas en “estado vacío”
  - Preparar caches/atributos internos

- ❌ **Prohibido**
  - Mostrar `QMessageBox` (warnings/errores) al iniciar sin proyecto cargado
  - Ejecutar cálculos pesados del motor (engine) / orquestación
  - Leer/escribir archivos de proyecto

### ¿Cuándo sí se calcula?
- Al cargar un proyecto (`DataModel.emit('project_loaded', ...)`)
- Al cambiar una sección lógica (`DataModel.notify_section_changed(Section.X)`), gestionado por `services/section_orchestrator.py`.

## Contrato DataModel ↔ UI

`DataModel` es la **fuente única de verdad**. La UI debe:

- Modificar `data_model.proyecto[...]` / `data_model.instalaciones[...]` / etc.
- Llamar `data_model.notify_section_changed(Section.XXX)` tras cambios relevantes.
- **Nunca** asumir que el proyecto está completo al iniciar.

Eventos disponibles (event bus):
- `project_loaded(file_path, data)`
- `project_saved(file_path)`
- `section_changed(section)`

## Contrato de refresco

- La UI **no** debe llamar recálculos globales en `__init__`.
- Si una pantalla necesita mostrar algo al inicio, debe usar un **placeholder**:
  - “Proyecto no cargado (sin cálculo)”
- Tras `project_loaded`, el orquestador llama los refresh necesarios.

## Tema/QSS: punto único

- El QSS se aplica **solo** en `main.py` vía `ui/theme.py::apply_app_theme(app)`.
- Las pantallas **no** deben aplicar estilos por su cuenta.
- `infra/paths.py` resuelve rutas tanto en modo dev como en modo frozen (PyInstaller).

## Checklist rápido (cuando algo “no carga”)

1. ¿Se disparó `project_loaded` al cargar archivo?
2. ¿La pantalla depende de datos del proyecto dentro de `__init__`? (mover a refresh post-load)
3. ¿Se emitió `notify_section_changed(Section.X)` al editar?
4. ¿El orquestador tiene el mapeo de refresh correcto?



## Checks de arquitectura

- Ejecuta `python tools/check_architecture.py` para validar límites de capas.
