# -*- coding: utf-8 -*-
"""Issue a signed JWT token for SSAA.

The app verifies the token using LICENSE_PUBLIC_KEY_PEM and applies:
  - enabled=false => kill switch (no grace)
  - exp => expiry

Usage example:
  python tools/license_issuer/issue_token.py \
    --private-key tools/license_issuer/keys/private_key.pem \
    --out token.jwt \
    --enabled true \
    --expires-days 30 \
    --edition pro
"""

from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict

import jwt


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _detect_alg(private_pem: str, algo_arg: str | None) -> str:
    if algo_arg:
        return algo_arg
    # Heuristic: Ed25519 private keys are usually PKCS8 and contain no "RSA".
    # We let PyJWT/cryptography validate it; default to RS256.
    return "RS256"


def _parse_features(features_json: str) -> Dict[str, Any]:
    if not features_json:
        return {}
    try:
        data = json.loads(features_json)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def issue_token(
    private_key_pem: str,
    enabled: bool,
    expires_days: int,
    edition: str,
    features: Dict[str, Any],
    iss: str,
    aud: str,
    license_id: str,
    algorithm: str,
) -> str:
    now = datetime.now(timezone.utc)
    payload: Dict[str, Any] = {
        "iss": iss,
        "aud": aud,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=max(1, expires_days))).timestamp()),
        "license_id": license_id,
        "enabled": bool(enabled),
        "edition": edition or "pro",
    }
    if features:
        payload["features"] = features

    token = jwt.encode(payload, private_key_pem, algorithm=algorithm)
    # pyjwt may return bytes in older versions; normalize.
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--private-key", required=True, help="Path to PEM private key")
    ap.add_argument("--out", required=True, help="Output file path (token text)")
    ap.add_argument("--enabled", default="true", choices=["true", "false"], help="Kill switch flag")
    ap.add_argument("--expires-days", type=int, default=30)
    ap.add_argument("--edition", default="pro")
    ap.add_argument("--features-json", default="", help="JSON dict string with feature flags")
    ap.add_argument("--iss", default="SSAA")
    ap.add_argument("--aud", default="SSAA-CLIENT")
    ap.add_argument("--license-id", default="", help="Optional explicit UUID")
    ap.add_argument("--algorithm", default="", help="Override algorithm (RS256, EdDSA, ES256)")
    args = ap.parse_args()

    priv_path = Path(args.private_key)
    out_path = Path(args.out)
    private_pem = _read_text(priv_path)

    algorithm = _detect_alg(private_pem, args.algorithm.strip() or None)
    enabled = args.enabled.strip().lower() == "true"
    features = _parse_features(args.features_json)
    license_id = args.license_id.strip() or str(uuid.uuid4())

    token = issue_token(
        private_key_pem=private_pem,
        enabled=enabled,
        expires_days=args.expires_days,
        edition=args.edition,
        features=features,
        iss=args.iss,
        aud=args.aud,
        license_id=license_id,
        algorithm=algorithm,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(token, encoding="utf-8")
    print(f"Token written to: {out_path}")
    print(f"license_id: {license_id}")
    print(f"enabled: {enabled}")
    print(f"expires_days: {args.expires_days}")
    print(f"algorithm: {algorithm}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
