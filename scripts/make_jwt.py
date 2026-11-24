#!/usr/bin/env python3
"""G2: mint a demo HS256 JWT for the Payments jwt plugin.

Uses PyJWT, pinned in `requirements-dev.txt`. Kong's jwt plugin verifies the
signature with the consumer's `secret` and matches the `key` against the
token `iss` claim, so --iss must be fintech-free or fintech-premium to
authenticate.

Examples:
  python scripts/make_jwt.py --iss fintech-free
  python scripts/make_jwt.py --iss fintech-free --bad-signature   # expect 401
"""

from __future__ import annotations

import argparse
import time
import warnings

try:
    import jwt
    from jwt.warnings import InsecureKeyLengthWarning
except ImportError as exc:  # pragma: no cover - dependency guard
    raise SystemExit(
        "PyJWT is required: python -m pip install -r requirements-dev.txt"
    ) from exc

# The committed secrets are deliberate short demo fixtures, not real keys.
warnings.filterwarnings("ignore", category=InsecureKeyLengthWarning)

SECRETS = {
    "fintech-free": "free-jwt-secret",
    "fintech-premium": "premium-jwt-secret",
}


def make_jwt(issuer: str, secret: str, ttl: int = 300, tamper: bool = False) -> str:
    """Return a signed HS256 JWT; tamper=True signs with a deliberately wrong key."""
    now = int(time.time())
    payload = {"iss": issuer, "iat": now, "exp": now + ttl}
    signing_secret = secret + "-tampered" if tamper else secret
    return jwt.encode(
        payload,
        signing_secret,
        algorithm="HS256",
        headers={"typ": "JWT"},
    )


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
