# License Issuer (SSAA)

Este directorio contiene herramientas **offline** para:

1) generar llaves (privada/pública) y
2) emitir un **token JWT firmado**

que luego publicas (por ejemplo) en OneDrive/SharePoint.

La aplicación (en `LICENSE_MODE = "cloud"`) descargará el token desde `LICENSE_TOKEN_URL`, verificará la firma con `LICENSE_PUBLIC_KEY_PEM` y aplicará:

- **Kill switch**: si el token viene con `enabled=false`, la app se bloquea **sin grace period**.
- **Grace period**: si OneDrive está caído, permite correr hasta `LICENSE_GRACE_DAYS` desde el último OK.

## Requisitos

- Python 3.10+
- Paquetes: `pyjwt` y `cryptography` (ya están en el entorno de desarrollo del proyecto).

## 1) Generar llaves

Desde la raíz del proyecto:

```bash
python tools/license_issuer/generate_keys.py --out-dir tools/license_issuer/keys --algo rsa
```

Esto crea:

- `tools/license_issuer/keys/private_key.pem`
- `tools/license_issuer/keys/public_key.pem`

> **Importante:**
> - La **privada** no se comparte nunca.
> - La **pública** es la que debes pegar en `app/config.py` (`LICENSE_PUBLIC_KEY_PEM`).

## 2) Emitir un token

Ejemplo (licencia válida 30 días):

```bash
python tools/license_issuer/issue_token.py \
  --private-key tools/license_issuer/keys/private_key.pem \
  --out token.jwt \
  --enabled true \
  --expires-days 30 \
  --edition pro
```

Para activar el **kill switch** remoto:

```bash
python tools/license_issuer/issue_token.py \
  --private-key tools/license_issuer/keys/private_key.pem \
  --out token.jwt \
  --enabled false \
  --expires-days 365
```

## 3) Publicar el token

1) Sube `token.jwt` a OneDrive/SharePoint
2) Obtén un link de descarga directa (HTTPS)
3) En `app/config.py` define:

```py
LICENSE_MODE = "cloud"
LICENSE_TOKEN_URL = "<TU_URL>"
LICENSE_PUBLIC_KEY_PEM = """-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----"""
```

## 4) Operación diaria (tu "switch")

- **Build libre:** `LICENSE_MODE = "offline"` (cambia 1 parámetro)
- **Build protegido:** `LICENSE_MODE = "cloud"`
- **Cortar acceso:** vuelve a emitir un token con `enabled=false` y reemplaza el archivo remoto.
