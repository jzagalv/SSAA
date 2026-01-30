param(
  [ValidateSet("offline","cloud")]
  [string]$Mode = "offline",
  [string]$TokenUrl = "",
  [string]$PublicKeyPemPath = "",
  [switch]$Obfuscate
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$projRoot = Split-Path -Parent $root
$spec = Join-Path $root "ssaa.spec"
$inno = Join-Path $root "inno\SSAA_installer.iss"

# Write build_config.json that will be bundled by PyInstaller.
$buildConfigPath = Join-Path $root "build_config.json"
$pubKey = ""
if ($PublicKeyPemPath -and (Test-Path $PublicKeyPemPath)) {
  $pubKey = Get-Content -Raw -Path $PublicKeyPemPath
}

$cfg = @{
  LICENSE_MODE = $Mode
  LICENSE_GRACE_DAYS = 7
  LICENSE_TOKEN_URL = $TokenUrl
  LICENSE_PUBLIC_KEY_PEM = $pubKey
}
$cfg | ConvertTo-Json -Depth 5 | Out-File -Encoding utf8 -FilePath $buildConfigPath

# Generate version artifacts for PyInstaller/Inno from version.json
python (Join-Path $root "generate_version_artifacts.py")


function Invoke-PyArmorObfuscation([string]$SourceRoot, [string]$OutRoot) {
  if (Test-Path $OutRoot) { Remove-Item -Recurse -Force $OutRoot }
  New-Item -ItemType Directory -Path $OutRoot | Out-Null

  Write-Host "== PyArmor obfuscation =="
  # Support PyArmor v8+ (gen) and legacy (obfuscate)
  $pyarmorCmd = "pyarmor"
  $hasGen = $false
  try {
    $help = & $pyarmorCmd --help 2>$null
    if ($help -match "\bgen\b") { $hasGen = $true }
  } catch {
    throw "PyArmor no encontrado en PATH. Instala con: pip install pyarmor"
  }

  if ($hasGen) {
    # Obfuscate everything reachable from entry script.
    & $pyarmorCmd gen --recursive -O $OutRoot (Join-Path $SourceRoot "main.py")
  } else {
    & $pyarmorCmd obfuscate --recursive -O $OutRoot (Join-Path $SourceRoot "main.py")
  }

  # Copy non-python resources that PyArmor doesn't reproduce.
  Copy-Item -Recurse -Force (Join-Path $SourceRoot "resources") (Join-Path $OutRoot "resources")
  if (-not (Test-Path (Join-Path $OutRoot "build"))) { New-Item -ItemType Directory -Path (Join-Path $OutRoot "build") | Out-Null }
  Copy-Item -Force (Join-Path $SourceRoot "build\build_config.json") (Join-Path $OutRoot "build\build_config.json")
  Copy-Item -Force (Join-Path $SourceRoot "build\version_info.txt") (Join-Path $OutRoot "build\version_info.txt")

  # Also copy any base libs shipped with the repo (optional).
  if (Test-Path (Join-Path $SourceRoot "base_libs")) {
    Copy-Item -Recurse -Force (Join-Path $SourceRoot "base_libs") (Join-Path $OutRoot "base_libs")
  }
}

$srcRootForBuild = $projRoot
if ($Obfuscate) {
  $obfRoot = Join-Path $root "_obf_src"
  Invoke-PyArmorObfuscation -SourceRoot $projRoot -OutRoot $obfRoot
  $srcRootForBuild = $obfRoot
}

Write-Host "== PyInstaller build (Mode=$Mode) =="
$env:SSAA_SRC_ROOT = $srcRootForBuild
pyinstaller $spec
$env:SSAA_SRC_ROOT = $null

Write-Host "== Inno Setup compile =="
$ISCC = $env:ISCC
if (-not $ISCC) { $ISCC = "ISCC.exe" }
& $ISCC $inno

Write-Host "Done."
