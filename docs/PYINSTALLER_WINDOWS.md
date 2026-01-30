# Build Windows (PyInstaller)

Compilación de ejecutable en Windows usando PyInstaller.

## Requisitos
- Windows 10/11
- Python 3.11+ (ideal igual al que usas en desarrollo)
- `pip install -e .`
- `pip install pyinstaller`

## Build (PowerShell)
Ejecuta desde la raíz del repo:

```powershell
./scripts/build_pyinstaller.ps1
```

## Resultado
- Ejecutable: `dist/SSAA/SSAA.exe`

## Recursos
El spec incluye `resources/` (QSS, iconos, etc.). Si agregas nuevos recursos, añádelos a la sección `datas` del `.spec`.

