$ErrorActionPreference = "Stop"

Write-Host "[SSAA] Building with PyInstaller..." -ForegroundColor Cyan

# Ensure we run from repo root
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $root
Set-Location $root

# Optional: clean previous builds
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
if (Test-Path "build") { 
    # keep build/inno; only remove pyinstaller build cache
    if (Test-Path "build\SSAA") { Remove-Item -Recurse -Force "build\SSAA" }
}

pyinstaller .\build\pyinstaller\ssaa.spec

Write-Host "[SSAA] Done. Output in dist\SSAA" -ForegroundColor Green
