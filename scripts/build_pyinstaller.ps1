$ErrorActionPreference = 'Stop'
Write-Host "[SSAA] PyInstaller build" -ForegroundColor Cyan

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

python -m pip install -e . | Out-Null
python -m pip install pyinstaller | Out-Null

pyinstaller -y build/pyinstaller/SSAA.spec

Write-Host "Build OK: dist/SSAA/SSAA.exe" -ForegroundColor Green
