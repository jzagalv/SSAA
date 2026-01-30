# SSAA Installer (per-user, no admin) - 1.4.0-alpha.40

## Build installer (recommended)

### Offline (free build)
```powershell
.\build\package_installer.ps1 -Mode offline
```

### Cloud license build
```powershell
.\build\package_installer.ps1 -Mode cloud `
  -TokenUrl "https://.../token.jwt" `
  -PublicKeyPemPath ".\tools\license_issuer\keys\public_key.pem"
```

### Add obfuscation (PyArmor)

Install PyArmor first:
```powershell
pip install pyarmor
```

Then:
```powershell
.\build\package_installer.ps1 -Mode cloud -Obfuscate `
  -TokenUrl "https://.../token.jwt" `
  -PublicKeyPemPath ".\tools\license_issuer\keys\public_key.pem"
```

Installs to `%LOCALAPPDATA%\Programs\SSAA` without admin.
