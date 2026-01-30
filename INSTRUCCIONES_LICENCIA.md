# Instrucciones: Licencia cloud + Kill switch (SSAA)

Este documento resume **paso a paso** cómo operar la licencia del programa.

## Objetivo

- Controlar la ejecución mediante un **token JWT firmado** alojado en la nube (OneDrive/SharePoint u otro hosting HTTPS).
- Permitir operar sin internet con **grace period** de 7 días.
- Permitir deshabilitar el programa remotamente (**kill switch**) sin re-compilar.

> Nota: la “protección” de código (ofuscación/compilación) es un paso posterior. Aquí dejamos el sistema listo para licenciamiento.

---

## 1) Preparar llaves (una sola vez)

1. Abre una terminal en la raíz del proyecto.
2. Genera llaves:

```bash
python tools/license_issuer/generate_keys.py --out-dir tools/license_issuer/keys --algo rsa
```

Se crean:

- `tools/license_issuer/keys/private_key.pem`  (NO compartir)
- `tools/license_issuer/keys/public_key.pem`   (se copia al código)

3. Copia el contenido de `public_key.pem` y pégalo en `app/config.py` en:

```py
LICENSE_PUBLIC_KEY_PEM = """-----BEGIN PUBLIC KEY-----
...
-----END PUBLIC KEY-----"""
```

---

## 2) Emitir token (cada vez que quieras renovar/cambiar licencia)

Ejemplo: licencia habilitada por 30 días:

```bash
python tools/license_issuer/issue_token.py \
  --private-key tools/license_issuer/keys/private_key.pem \
  --out token.jwt \
  --enabled true \
  --expires-days 30 \
  --edition pro
```

El archivo `token.jwt` es texto plano (JWT).

---

## 3) Publicar token (OneDrive/SharePoint)

1. Sube `token.jwt` a OneDrive/SharePoint.
2. Obtén una URL de descarga directa HTTPS.
3. En `app/config.py` configura:

```py
LICENSE_MODE = "cloud"
LICENSE_TOKEN_URL = "<URL_DEL_TOKEN_JWT>"
```

> Para una compilación libre, deja `LICENSE_MODE = "offline"` (cambias 1 parámetro).

---

## 4) Kill switch (deshabilitar remotamente)

Para cortar acceso, emite un token con `enabled=false` y reemplaza el archivo remoto:

```bash
python tools/license_issuer/issue_token.py \
  --private-key tools/license_issuer/keys/private_key.pem \
  --out token.jwt \
  --enabled false \
  --expires-days 365
```

**Importante:** cuando `enabled=false`, la app se bloquea **sin grace period**.

---

## 5) Grace period (7 días) y anti-rollback

- Si el token no se puede descargar (sin internet), la app permite funcionar hasta 7 días desde la última validación correcta.
- Si se detecta que el reloj del sistema fue movido hacia atrás (rollback), se deshabilita el grace y se exige validación online.

---

## 6) Parámetros (resumen)

En `app/config.py`:

- `LICENSE_MODE`: `"offline"` o `"cloud"`
- `LICENSE_GRACE_DAYS`: 7
- `LICENSE_TOKEN_URL`: URL del token publicado
- `LICENSE_PUBLIC_KEY_PEM`: clave pública para verificar la firma

---

## 7) Checklist de operación

1) ¿Quiero build libre? → `LICENSE_MODE="offline"`

2) ¿Quiero build protegido?
   - `LICENSE_MODE="cloud"`
   - token publicado y URL actual
   - clave pública pegada

3) ¿Quiero bloquear a todos? → token `enabled=false` y reemplazar remoto.


## Compilar instalador en modo OFFLINE vs CLOUD (un parámetro)

El instalador copia el build generado por PyInstaller. Para cambiar entre compilación libre (offline) y protegida (cloud)
sin editar código, usa el script `build/package_installer.ps1`:

```powershell
# Compilación libre
.\build\package_installer.ps1 -Mode offline

# Compilación con licencia (token remoto)
.\build\package_installer.ps1 -Mode cloud -TokenUrl "https://.../token.jwt" -PublicKeyPemPath ".\tools\license_issuer\keys\public_key.pem"
```

El script genera `build/build_config.json`, que es incluido dentro del ejecutable como `build_config.json`.
En runtime, `app/config.py` lo lee y sobre-escribe `LICENSE_MODE`, `LICENSE_TOKEN_URL`, etc.

### Archivos locales (para grace y anti-manipulación)
- `%APPDATA%\SSAA\license_cache.json`: cache firmado del último OK.
- `%APPDATA%\SSAA\license_state.json`: estado firmado (contador/hash-chain + huella del ejecutable).
- `%APPDATA%\SSAA\license_secret.bin`: secreto local per-user usado para firmar cache/estado.

Notas:
- Si se detecta manipulación (firma inválida), o cambios de ejecutable, o rollback del reloj, **se deshabilita el grace** y se exige validación en línea.

