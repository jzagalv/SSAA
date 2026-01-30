# Packaging en Windows (PyInstaller)

Esta receta empaqueta la app en un ejecutable Windows, incluyendo `resources/` (QSS, íconos) y archivos necesarios.

## Requisitos

- Python 3.10+ (recomendado)
- PyQt5 instalado
- PyInstaller instalado

Ejemplo:

```
pip install -U pyinstaller
pip install -r requirements.txt
```

## Build

Desde la raíz del repo:

### Opción 1: usando el `.spec`

```
pyinstaller build/pyinstaller/ssaa.spec --noconfirm
```

Salida típica:

- `dist/SSAA/SSAA.exe`

### Opción 2: script PowerShell

```
powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1
```

## Notas

- Si usas QSS/íconos, valida que `resources/` quede incluido.
- Si PyInstaller no encuentra archivos, revisa `datas` en el `.spec`.
