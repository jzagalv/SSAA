# Guía de escalabilidad (pantallas, cálculos y enlaces de datos)

## Crear una pantalla nueva (scaffold)
1. Desde la raíz del repo:
```bash
python tools/scaffold/create_screen.py --name "Mi Pantalla" --module mi_pantalla --section PROJECT
```

2. Registra la pantalla en `app/controller.py`:
- crear instancia
- agregar a tabs/stack
- conectar `data_changed` a `data_model.notify_section_changed(Section.X)` si corresponde

3. Mantén la regla:
- **UI en `*_screen.py`**
- **orquestación en `*_controller.py`**
- **cálculos puros en `core/`**
- **validaciones en `core/validators`**
- **I/O (archivos) en `storage/`**
- **integración (rutas, logs, config) en `infra/`**

## Añadir cálculos
- Preferir funciones puras en `core/calculations/`
- Retornar `Result`/dataclasses sin tocar UI
- Los controladores consumen estos outputs y actualizan widgets

## Enlaces de datos (DataModel)
- DataModel es el “single source of truth”.
- Cambios → `notify_section_changed(Section.XXX)` y refresco por orquestador.

## Tests de contrato
- Cada pantalla debe declarar `SECTION = Section.X`.
- Evitar imports circulares. Mantener dependencias en una dirección:
  `screens -> services -> core/domain -> infra/storage` (UI no debe depender de storage directo).


## Scaffold de feature (cálculo + validator)

Puedes generar la base de un feature sin UI con:

```bash
python tools/scaffold/create_feature.py --name mi_feature
```

Luego sigue el checklist en `tools/scaffold/WIRING_CHECKLIST.md`.
