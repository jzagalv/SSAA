# Release check (Stage 1)

Run from the repo root.

## Quick smoke (compile + tests)
```powershell
powershell -ExecutionPolicy Bypass -File scripts\release_check.ps1
```

## With PyInstaller build (onedir)
```powershell
$env:SSAA_BUILD=1
powershell -ExecutionPolicy Bypass -File scripts\release_check.ps1
```

## With installer (Inno Setup)
Requires `ISCC.exe` available in PATH (Inno Setup installed).

```powershell
$env:SSAA_BUILD=1
$env:SSAA_INSTALLER=1
powershell -ExecutionPolicy Bypass -File scripts\release_check.ps1
```

## Performance tracing
Enable `perf.log` timings:
```powershell
$env:SSAA_PERF=1
python main.py
```

Logs are written to `%APPDATA%\SSAA\logs\perf.log`.
