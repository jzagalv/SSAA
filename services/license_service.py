# -*- coding: utf-8 -*-
"""License checking (cloud token + grace).

Design goals
------------
- Easy to disable for a "free" build (one parameter in `app/config.py`).
- In "cloud" mode, validate a remote signed token (JWT recommended).
- Allow a grace period (default 7 days) if cloud is temporarily unavailable.
- Best-effort protection against **system clock rollback** (anti-grace abuse).

This module has **no PyQt imports**. UI code should interpret the result
and display messages / exit / enter demo mode.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import logging
import os
import sys
import base64
import hashlib
import hmac
import secrets
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import jwt  # PyJWT

# NOTE: this service can be imported very early (even before app/bootstrap
# injects the project root into sys.path). In development, users may run the
# app from arbitrary working directories (shortcuts / IDE / scripts). Make this
# module self-sufficient by ensuring the project root is on sys.path.
try:
    from app.config import (
        LICENSE_MODE,
        LICENSE_GRACE_DAYS,
        LICENSE_PUBLIC_KEY_PEM,
        LICENSE_TOKEN_URL,
    )
except ModuleNotFoundError:
    try:
        from infra.paths import app_root

        root = str(app_root())
        if root and root not in sys.path:
            sys.path.insert(0, root)
        from app.config import (
            LICENSE_MODE,
            LICENSE_GRACE_DAYS,
            LICENSE_PUBLIC_KEY_PEM,
            LICENSE_TOKEN_URL,
        )
    except Exception as e:  # pragma: no cover (fatal mispackage/dev env)
        raise ModuleNotFoundError(
            "Could not import app.config. Ensure project root is on PYTHONPATH."
        ) from e

log = logging.getLogger(__name__)


@dataclass
class LicenseStatus:
    ok: bool
    reason: str
    grace_days_left: int = 0
    payload: Optional[Dict[str, Any]] = None


def _cache_path() -> Path:
    # Per-user cache (no admin): %APPDATA%\SSAA\license_cache.json
    appdata = os.environ.get("APPDATA") or str(Path.home())
    p = Path(appdata) / "SSAA"
    p.mkdir(parents=True, exist_ok=True)
    return p / "license_cache.json"

def _state_path() -> Path:
    """Per-user signed state used to prevent grace abuse via cache rollback."""
    appdata = os.environ.get("APPDATA") or str(Path.home())
    p = Path(appdata) / "SSAA"
    p.mkdir(parents=True, exist_ok=True)
    return p / "license_state.json"


def _canonical_bytes(obj: Dict[str, Any]) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sign_obj(payload: Dict[str, Any], secret: bytes) -> str:
    mac = hmac.new(secret, _canonical_bytes(payload), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac).decode("ascii").rstrip("=")


def _verify_obj(obj: Dict[str, Any], secret: bytes) -> bool:
    sig = obj.get("_sig")
    if not sig:
        return False
    payload = dict(obj)
    payload.pop("_sig", None)
    expected = _sign_obj(payload, secret)
    return hmac.compare_digest(str(sig), str(expected))


def _load_state() -> Tuple[Dict[str, Any], bool]:
    p = _state_path()
    if not p.exists():
        return {}, False
    try:
        raw = json.loads(p.read_text(encoding="utf-8") or "{}")
        if not isinstance(raw, dict):
            return {}, False
        secret = _get_or_create_secret()
        if _verify_obj(raw, secret):
            return raw, True
        return raw, False
    except Exception:
        return {}, False


def _save_state(state: Dict[str, Any]) -> None:
    try:
        state = dict(state or {})
        state["last_seen_utc"] = datetime.now(timezone.utc).isoformat()
        secret = _get_or_create_secret()
        payload = dict(state)
        payload.pop("_sig", None)
        payload["_sig"] = _sign_obj({k: v for k, v in payload.items() if k != "_sig"}, secret)
        _state_path().write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        log.debug("Failed to save license state", exc_info=True)



def _secret_path() -> Path:
    # Per-user secret used to sign the cache against casual tampering.
    # Stored alongside the cache to avoid requiring admin permissions.
    p = _cache_path().parent / "license_secret.bin"
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return p


def _get_or_create_secret() -> bytes:
    p = _secret_path()
    if p.exists():
        try:
            b = p.read_bytes()
            if len(b) >= 16:
                return b
        except Exception:
            pass
    # Create a new random secret (32 bytes)
    try:
        b = secrets.token_bytes(32)
        p.write_bytes(b)
        return b
    except Exception:
        # Last resort: derive something stable-ish (we still treat cache as untrusted)
        return (os.environ.get("USERNAME", "") + str(Path.home())).encode("utf-8")[:32].ljust(32, b"\0")


def _canonical_cache_bytes(cache: Dict[str, Any]) -> bytes:
    # Sign a canonical JSON representation (sorted keys, compact separators)
    return json.dumps(cache, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sign_cache(payload: Dict[str, Any], secret: bytes) -> str:
    mac = hmac.new(secret, _canonical_cache_bytes(payload), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac).decode("ascii").rstrip("=")


def _verify_cache(cache: Dict[str, Any], secret: bytes) -> bool:
    sig = cache.get("_sig")
    if not sig:
        return False
    payload = dict(cache)
    payload.pop("_sig", None)
    expected = _sign_cache(payload, secret)
    # Constant-time compare
    return hmac.compare_digest(str(sig), expected)


def _load_cache() -> Tuple[Dict[str, Any], bool]:
    """Load cache and verify its signature.

    Returns (cache, is_trusted). If untrusted, the caller must NOT grant grace
    based on the cache contents.
    """
    p = _cache_path()
    if not p.exists():
        return {}, False
    try:
        cache = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(cache, dict):
            return {}, False
    except Exception:
        return {}, False

    try:
        secret = _get_or_create_secret()
        if _verify_cache(cache, secret):
            return cache, True
        # Signature missing/invalid -> treat as untrusted
        return cache, False
    except Exception:
        return cache, False


def _save_cache(cache: Dict[str, Any]) -> None:
    """Save cache with a signature (best-effort)."""
    try:
        cache = dict(cache or {})
        cache["last_seen_utc"] = datetime.now(timezone.utc).isoformat()
        secret = _get_or_create_secret()
        payload = dict(cache)
        payload.pop("_sig", None)
        payload["_sig"] = _sign_cache({k: v for k, v in payload.items() if k != "_sig"}, secret)
        _cache_path().write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        log.debug("Failed to save license cache", exc_info=True)


def _exe_sha256() -> str:
    """Best-effort SHA256 of the running executable/script."""
    try:
        # In PyInstaller, sys.executable points to the bundled exe.
        p = Path(getattr(sys, "executable", "") or "")
        if not p.exists():
            p = Path(sys.argv[0])
        if not p.exists():
            return ""
        h = hashlib.sha256()
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""


def _clock_rollback_detected(cache: Dict[str, Any], cache_trusted: bool) -> bool:
    """Detect time rollback (best-effort).

    If cache is untrusted (tampered), we disable grace by treating it as rollback.
    Otherwise, detect significant backward jumps relative to our last_seen/last_ok.
    """
    if not cache_trusted and cache:
        return True
    try:
        now = datetime.now(timezone.utc)
        prev_candidates = []
        for k in ("last_seen_utc", "last_ok_utc"):
            v = cache.get(k)
            if not v:
                continue
            dt = datetime.fromisoformat(v)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            prev_candidates.append(dt)
        if not prev_candidates:
            return False
        prev = max(prev_candidates)
        # Allow small drift (5 minutes)
        return now < (prev - timedelta(minutes=5))
    except Exception:
        return False


def _fetch_remote_token() -> Tuple[bool, str]:
    """Fetch token text from LICENSE_TOKEN_URL (HTTPS direct download)."""
    url = (LICENSE_TOKEN_URL or "").strip()
    if not url:
        return False, "LICENSE_TOKEN_URL not configured"
    try:
        # Use stdlib (no extra deps)
        import urllib.request

        req = urllib.request.Request(url, headers={"User-Agent": "SSAA/LicenseChecker"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = resp.read()
        text = data.decode("utf-8", errors="replace").strip()
        if not text:
            return False, "Empty token content"
        return True, text
    except Exception as e:
        return False, f"Fetch failed: {e}"


def _verify_token(token_text: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """Verify a signed token.

    Recommended format: JWT signed with EdDSA (Ed25519) or RS256.

    Payload contract (recommended):
      - enabled: bool (kill switch)
      - exp: unix timestamp (expiry)
      - iat: unix timestamp (issued at)
      - edition/features: optional
    """
    public_key = (LICENSE_PUBLIC_KEY_PEM or "").strip()
    if not public_key:
        return False, "LICENSE_PUBLIC_KEY_PEM not configured", None

    # Try common algorithms; the public key determines what works.
    algs = ["EdDSA", "RS256", "ES256"]
    try:
        payload = jwt.decode(
            token_text,
            public_key,
            algorithms=algs,
            options={
                "verify_signature": True,
                "verify_exp": True,
            },
        )
        if not isinstance(payload, dict):
            return False, "Invalid payload type", None

        # Kill switch (remote disable)
        enabled = payload.get("enabled", True)
        if enabled is False:
            return False, "Disabled remotely (kill switch)", payload

        return True, "OK", payload
    except jwt.ExpiredSignatureError:
        return False, "Token expired", None
    except jwt.InvalidTokenError as e:
        return False, f"Invalid token: {e}", None
    except Exception as e:
        return False, f"Verify error: {e}", None


def check_license(force_online: bool = False) -> LicenseStatus:
    """Validate license according to LICENSE_MODE.

    Args:
        force_online: If True, do not use grace/cached allowance; require an online validation.


    Returns:
        LicenseStatus(ok=True) when allowed to run.
        LicenseStatus(ok=False) when blocked.
    """
    mode = (LICENSE_MODE or "offline").strip().lower()

    if mode == "offline":
        return LicenseStatus(ok=True, reason="offline mode (free build)")

    cache, cache_trusted = _load_cache()
    state, state_trusted = _load_state()
    rollback = _clock_rollback_detected(cache, cache_trusted)

    # Additional anti-tamper: if executable changed since last OK, disable grace.
    exe_hash = _exe_sha256()
    prev_exe_hash = (state.get("exe_sha256") if isinstance(state, dict) else None) or cache.get("exe_sha256")
    exe_mismatch = bool(prev_exe_hash) and bool(exe_hash) and (prev_exe_hash != exe_hash)
    if exe_mismatch:
        cache["last_fail_reason"] = "Executable changed; grace disabled"
        _save_cache(cache)
        _save_state(state)
        return LicenseStatus(ok=False, reason="Se detectó cambio en el ejecutable. Se requiere validar en línea.", grace_days_left=0)


    # 1) Try online token
    ok, token_or_reason = _fetch_remote_token()
    if ok:
        v_ok, v_reason, payload = _verify_token(token_or_reason)
        if v_ok:
            cache["last_ok_utc"] = datetime.now(timezone.utc).isoformat()
            cache["last_ok_reason"] = v_reason
            cache["last_ok_payload"] = payload or {}

            # Update anti-tamper state (monotonic counter + hash chain + exe fingerprint)
            try:
                counter = int((state or {}).get("ok_counter") or 0) + 1
            except Exception:
                counter = 1
            prev_hash = str((state or {}).get("ok_chain_hash") or "")
            license_id = str((payload or {}).get("license_id") or "")
            exp = (payload or {}).get("exp")
            enabled_flag = (payload or {}).get("enabled", True)
            material = f"{prev_hash}|{license_id}|{exp}|{enabled_flag}|{exe_hash}|{counter}".encode("utf-8")
            chain_hash = hashlib.sha256(material).hexdigest()

            cache["ok_counter"] = counter
            cache["ok_chain_hash"] = chain_hash
            cache["exe_sha256"] = exe_hash

            state = dict(state or {})
            state["ok_counter"] = counter
            state["ok_chain_hash"] = chain_hash
            state["exe_sha256"] = exe_hash
            state["last_ok_utc"] = cache["last_ok_utc"]

            _save_cache(cache)
            _save_state(state)
            return LicenseStatus(ok=True, reason="validated", grace_days_left=int(LICENSE_GRACE_DAYS), payload=payload)
        else:
            # If token is explicitly disabled remotely, do NOT allow grace.
            if "kill switch" in v_reason.lower() or "disabled remotely" in v_reason.lower():
                cache["last_fail_reason"] = v_reason
                _save_cache(cache)
                _save_state(state)
                return LicenseStatus(ok=False, reason=v_reason, grace_days_left=0, payload=payload)

            cache["last_fail_reason"] = v_reason
            _save_cache(cache)
            # fall through to grace evaluation
            token_or_reason = v_reason

    




    # 2) Grace evaluation (no grace if rollback detected)
    if rollback:
        cache["last_fail_reason"] = "Clock rollback detected; grace disabled"
        _save_cache(cache)
        _save_state(state)
        return LicenseStatus(
            ok=False,
            reason="Reloj del sistema alterado (rollback). Se requiere validar en línea.",
            grace_days_left=0,
        )

    # If the caller requested a strict online check, do not fallback to grace.
    if force_online and not ok:
        msg = str(token_or_reason)
        cache["last_fail_reason"] = msg
        _save_cache(cache)
        _save_state(state)
        return LicenseStatus(ok=False, reason=msg, grace_days_left=0)

    try:
        # Security model: grace only if local cache/state are trustworthy and consistent.
        if not cache_trusted:
            raise RuntimeError("CACHE_UNTRUSTED")
        if not state_trusted:
            if not _state_path().exists():
                raise RuntimeError("STATE_MISSING")
            raise RuntimeError("STATE_UNTRUSTED")

        # Require state/cache consistency
        if cache.get("ok_counter") != state.get("ok_counter") or cache.get("ok_chain_hash") != state.get("ok_chain_hash"):
            raise RuntimeError("STATE_MISMATCH")
        if cache.get("exe_sha256") and exe_hash and cache.get("exe_sha256") != exe_hash:
            raise RuntimeError("EXE_MISMATCH")

        last_ok = cache.get("last_ok_utc")
        if last_ok:
            prev_ok = datetime.fromisoformat(last_ok)
            if prev_ok.tzinfo is None:
                prev_ok = prev_ok.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            delta = now - prev_ok
            grace_total = timedelta(days=int(LICENSE_GRACE_DAYS))
            if delta <= grace_total:
                days_left = max(0, int((grace_total - delta).total_seconds() // 86400))
                _save_cache(cache)
                return LicenseStatus(
                    ok=True,
                    reason=f"grace ({token_or_reason})",
                    grace_days_left=days_left,
                    payload=cache.get("last_ok_payload"),
                )
    except Exception as e:
        code = str(e)
        msg = None
        if code == "STATE_MISSING":
            msg = "Faltan archivos locales de licencia (se re-inicializó el estado). Conéctate a internet para revalidar."
        elif code == "CACHE_UNTRUSTED":
            msg = "Se detectó manipulación del cache de licencia. Se requiere validar en línea."
        elif code == "STATE_UNTRUSTED":
            msg = "Se detectó manipulación del estado local de licencia. Se requiere validar en línea."
        elif code == "STATE_MISMATCH":
            msg = "Inconsistencia en estado local de licencia. Se requiere validar en línea."
        elif code == "EXE_MISMATCH":
            msg = "El ejecutable cambió desde la última validación. Se requiere validar en línea."
        if msg:
            cache["last_fail_reason"] = msg
            _save_cache(cache)
            _save_state(state)
            return LicenseStatus(ok=False, reason=msg, grace_days_left=0)
        log.debug("Grace computation failed", exc_info=True)

    _save_cache(cache)
    _save_state(state)
    return LicenseStatus(ok=False, reason=f"License check failed: {token_or_reason}", grace_days_left=0)


def wipe_local_license_files() -> None:
    """Remove local license cache/state/secret (per-user).

    Used by 'Repair installation' flow to force a clean revalidation.
    """
    for p in (_cache_path(), _state_path(), _secret_path()):
        try:
            if p.exists():
                p.unlink()
        except Exception:
            pass
