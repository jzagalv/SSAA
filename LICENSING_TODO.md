# Licensing (TODO / Notes)

This project includes licensing infrastructure with **7-day grace** and rollback detection.

## Goals
1) Hide logic "at first glance" (later via PyArmor / Nuitka).
2) Enable/disable execution via a **remote signed token** (easy to revoke).
3) Allow building a "free" compilation by changing **one parameter**:
   - `LICENSE_MODE = "offline"` (free build)
   - `LICENSE_MODE = "cloud"` (licensed build)

## Current implementation
- Config: `app/config.py`
  - `LICENSE_MODE`, `LICENSE_GRACE_DAYS = 7`
  - `LICENSE_TOKEN_URL` (remote token text, HTTPS direct download)
  - `LICENSE_PUBLIC_KEY_PEM` (public key for signature verification)

- Checker: `services/license_service.py`
  - Fetches token from `LICENSE_TOKEN_URL`
  - Verifies signature (JWT): EdDSA / RS256 / ES256
  - Supports **grace** for 7 days if cloud is temporarily unavailable
  - Detects system clock rollback and disables grace for this run

## Kill switch (where it lives)
The kill switch is a **field inside the signed token payload**:

- `enabled: true`  -> application runs (if token valid and not expired)
- `enabled: false` -> application is **blocked immediately** (NO grace)

This means you can disable all clients by publishing a new token with:
```json
{ "enabled": false, "exp": 9999999999, "iat": 1234567890 }
```
signed with your private key.

## Remaining TODO (to go live)
1) Generate a keypair (recommended: Ed25519).
   - Keep the **private** key offline (signing only).
   - Embed the **public** key in `LICENSE_PUBLIC_KEY_PEM`.

2) Produce a JWT token with payload fields (recommended):
   - `enabled` (bool)
   - `exp` (expiry, unix timestamp)
   - `iat` (issued at, unix timestamp)
   - optional: `edition`, `features`, `customer`, `machine_limit`, etc.

3) Host the token text (raw JWT string) at a stable HTTPS URL
   - OneDrive/SharePoint direct download is OK to start.
   - The URL does NOT need to be secret; the token is signed.

4) Switch build:
   - set `LICENSE_MODE = "cloud"` in `app/config.py`
   - rebuild installer

## Notes
- Grace uses local clock, but rollback detection reduces trivial bypass.
- Determined attackers can still patch binaries. For stronger protection:
  - obfuscate with PyArmor before packaging
  - or migrate build to Nuitka

## Operator guide

See `INSTRUCCIONES_LICENCIA.md` for the step-by-step operational procedure.
