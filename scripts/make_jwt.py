#!/usr/bin/env python3
"""G2: mint a demo HS256 JWT for the Payments jwt plugin.

Uses only the Python standard library (PyJWT is not required). Kong's jwt
plugin verifies the signature with the consumer's `secret` and matches the
`key` against the token `iss` claim, so --iss must be fintech-free or
fintech-premium to authenticate.

Examples:
  python scripts/make_jwt.py --iss fintech-free
  python scripts/make_jwt.py --iss fintech-free --bad-signature   # expect 401
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import time

SECRETS = {
    "fintech-free": "free-jwt-secret",
    "fintech-premium": "premium-jwt-secret",
}


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def make_jwt(issuer: str, secret: str, ttl: int = 300, tamper: bool = False) -> str:
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"iss": issuer, "iat": now, "exp": now + ttl}
    head = b64url(json.dumps(header, separators=(",", ":")).encode())
    body = b64url(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{head}.{body}"
    signature = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    if tamper:
        signature = bytes([signature[0] ^ 0xFF]) + signature[1:]
    return f"{signing_input}.{b64url(signature)}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iss", default="fintech-free", choices=sorted(SECRETS))
    parser.add_argument("--secret", default=None, help="override the demo secret")
    parser.add_argument("--ttl", type=int, default=300)
    parser.add_argument("--bad-signature", action="store_true")
    args = parser.parse_args()

    secret = args.secret or SECRETS[args.iss]
    print(make_jwt(args.iss, secret, args.ttl, args.bad_signature))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
