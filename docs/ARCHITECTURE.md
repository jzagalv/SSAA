# Arquitectura SSAA

## 1. Capas

- **domain/**: modelos y fachada del proyecto (`ProjectFacade`). *No depende de PyQt.*
- **services/**: lógica de negocio y cálculos (por ejemplo CC, bank/charger, load tables). *No depende de PyQt.*
- **storage/**: I/O, serialización y migraciones (`upgrade_project_dict`).
- **infra/**: paths, logging, settings, crash handler.
- **app/**: bootstrap de la aplicación, wiring de alto nivel, versión.
- **ui/**: widgets/diálogos compartidos (PyQt).
- **screens/**: pantallas (PyQt). Solo UI + eventos.

## 2. Reglas de imports (límite de capas)

1) `domain` **no importa** `app`, `ui` ni `screens`.
2) `services` **no importa** `ui` ni `screens`.
3) `storage` puede importar `domain` y `infra`, pero **no** `ui`/`screens`.
4) `screens` puede importar `services`, `domain`, `storage` (idealmente vía controllers).

Estas reglas existen para que:
- los cálculos se prueben sin UI
- los cambios de UI no rompan el core
- las migraciones se mantengan estables

## 3. Patrón recomendado por pantalla

Para pantallas grandes:

- `..._screen.py`: layout + señales Qt + render.
- `..._controller.py`: flujo de eventos, `mark_dirty`, best-effort `safe_call`.
- `widgets.py`: builders/render helpers para tablas y componentes UI.
- `services/*`: cálculo y reglas.

## 4. Claves persistidas (schema)

- Usar **`core/keys.py`** como fuente única de keys persistidas.
- La UI no debería escribir keys profundas directamente; usar **`ProjectFacade`**.

## 5. Migraciones

- Las migraciones viven en `storage/migrations.py`.
- Deben ser **idempotentes** (aplicar dos veces no cambia el resultado).
- Cada cambio de schema importante debe venir con un sample `.ssaa` en `tests/data/`.

## 6. Calidad mínima (checklist)

- Services sin PyQt (testeables).
- Smoke tests sobre proyectos reales en `tests/data/`.
- `CHANGELOG.md` actualizado por versión.

