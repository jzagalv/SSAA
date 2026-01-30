# -*- coding: utf-8 -*-
"""Build-time configuration.

This module is intentionally tiny and *import-safe*.

Licensing strategy
------------------
- Set ``LICENSE_MODE = 'offline'`` to build a free/unlocked compilation.
- Set ``LICENSE_MODE = 'cloud'`` to enforce a remote token check with grace.

Goal: switch between free vs licensed builds by changing **one** parameter.

See ``LICENSING_TODO.md`` for steps to generate and host the token.
"""

from __future__ import annotations

# One-parameter switch:
#   - 'offline': skip checks (free build)
#   - 'cloud'  : enforce token check (+ grace)
LICENSE_MODE: str = "offline"

# Grace window when cloud validation cannot be completed.
# Anti-tamper is best-effort (rollback detection). See LICENSING_TODO.md.
LICENSE_GRACE_DAYS: int = 7

# Remote token URL (direct download HTTPS). Example:
#   https://.../download?...
LICENSE_TOKEN_URL: str = ""

# Public key for signature verification (PEM). Keep private key offline.
# Example (Ed25519/RSA/ECDSA public key in PEM):
#   -----BEGIN PUBLIC KEY-----
#   ...
#   -----END PUBLIC KEY-----
LICENSE_PUBLIC_KEY_PEM: str = ""


# --- Build overrides (optional) ---
# When packaging, the build pipeline may include a `build_config.json` resource.
# This allows switching between free/offline vs licensed/cloud builds without editing code.
try:
    import json
    from app.paths import resource_path
    _bc_path = resource_path("build_config.json")
    if _bc_path and __import__("os").path.exists(_bc_path):
        with open(_bc_path, "r", encoding="utf-8") as _f:
            _bc = json.load(_f) or {}
        # Allow overriding these settings from the build.
        LICENSE_MODE = str(_bc.get("LICENSE_MODE", LICENSE_MODE))
        LICENSE_GRACE_DAYS = int(_bc.get("LICENSE_GRACE_DAYS", LICENSE_GRACE_DAYS))
        LICENSE_TOKEN_URL = str(_bc.get("LICENSE_TOKEN_URL", LICENSE_TOKEN_URL))
        LICENSE_PUBLIC_KEY_PEM = str(_bc.get("LICENSE_PUBLIC_KEY_PEM", LICENSE_PUBLIC_KEY_PEM))
except Exception:
    # Never crash on config overrides.
    pass
