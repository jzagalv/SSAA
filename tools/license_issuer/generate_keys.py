# -*- coding: utf-8 -*-
"""Generate signing keypair for SSAA licensing.

Default: RSA 2048 (RS256).

Usage:
  python tools/license_issuer/generate_keys.py --out-dir tools/license_issuer/keys --algo rsa

Notes:
  - Keep private_key.pem secret.
  - public_key.pem is embedded in the app (LICENSE_PUBLIC_KEY_PEM).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def generate_rsa(out_dir: Path, bits: int = 2048) -> tuple[Path, Path]:
    priv = rsa.generate_private_key(public_exponent=65537, key_size=bits)
    priv_pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_pem = priv.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    priv_path = out_dir / "private_key.pem"
    pub_path = out_dir / "public_key.pem"
    _write(priv_path, priv_pem)
    _write(pub_path, pub_pem)
    return priv_path, pub_path


def generate_ed25519(out_dir: Path) -> tuple[Path, Path]:
    priv = ed25519.Ed25519PrivateKey.generate()
    priv_pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_pem = priv.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    priv_path = out_dir / "private_key.pem"
    pub_path = out_dir / "public_key.pem"
    _write(priv_path, priv_pem)
    _write(pub_path, pub_pem)
    return priv_path, pub_path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True, help="Directory to write PEM files")
    ap.add_argument("--algo", choices=["rsa", "ed25519"], default="rsa")
    ap.add_argument("--rsa-bits", type=int, default=2048)
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    if args.algo == "rsa":
        priv, pub = generate_rsa(out_dir, bits=args.rsa_bits)
        print(f"Generated RSA keypair (RS256) -> {priv} / {pub}")
    else:
        priv, pub = generate_ed25519(out_dir)
        print(f"Generated Ed25519 keypair (EdDSA) -> {priv} / {pub}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
