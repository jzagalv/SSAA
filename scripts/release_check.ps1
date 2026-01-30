# SSAA Release Check (Stage1)
# Run from repo root:
#   powershell -ExecutionPolicy Bypass -File scripts\release_check.ps1
#
# Optional env vars:
#   $env:SSAA_BUILD=1     -> run PyInstaller build
#   $env:SSAA_INSTALLER=1 -> run Inno Setup build (requires ISCC.exe in PATH)

$ErrorActionPreference = "Stop"

Write-Host "[1] Compile check" -ForegroundColor Cyan
python -m py_compile main.py

Write-Host "[2] Unit tests" -ForegroundColor Cyan
python -m pytest -q

Write-Host "[3] Generate version artifacts" -ForegroundColor Cyan
python build/generate_version_artifacts.py

if ($env:SSAA_BUILD -eq "1") {
  Write-Host "[4] PyInstaller build" -ForegroundColor Cyan
  python -m PyInstaller build/ssaa.spec --noconfirm
}

if ($env:SSAA_INSTALLER -eq "1") {
  Write-Host "[5] Inno Setup installer" -ForegroundColor Cyan
  ISCC.exe build\inno\SSAA_installer.iss
}

Write-Host "OK ✅" -ForegroundColor Green
