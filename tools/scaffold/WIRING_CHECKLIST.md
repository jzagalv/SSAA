# Wiring checklist (SSAA)

## 1) Feature sin UI (solo cálculo)
- Crear cálculo en `core/calculations/<feature>.py`
- (Opcional) wrapper en `services/<feature>_service.py`
- Registrar recalc en `app/section_registry.py` si debe reaccionar a un `Section`

## 2) Feature con validación
- Implementar `core/validators/<feature>_validator.py`
- Registrar en `services/validation_service.py` (map: Section -> validator)

## 3) Feature con pantalla nueva
- `python tools/scaffold/create_screen.py --name <feature>`
- Definir `SECTION = Section.<...>` en la pantalla
- Agregarla al controller/tab principal
- Registrar `SECTION_OWNERS` / `REFRESH_OWNERS` en `app/section_catalog.py`
- Si requiere refresh: registrar en `app/section_registry.py`

## 4) Build/installer
- Si agrega recursos (qss/icon/json/base_libs): añadir a `build/ssaa.spec` (datas)
- Correr `pyinstaller build/ssaa.spec`
- Si es cloud, probar `--revalidate` (Menú inicio) y Recovery
