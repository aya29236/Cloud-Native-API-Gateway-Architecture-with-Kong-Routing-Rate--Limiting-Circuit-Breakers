#!/usr/bin/env bash
# G2 (Student A): generate DEMO credentials for the JWT/key-auth lab.
# Real deployments must use a secret manager; these values are committed as
# demo fixtures only and must never be used outside this prototype.
set -euo pipefail

OUT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/demo_secrets"
mkdir -p "$OUT"

printf '%s\n' 'free-jwt-secret' > "$OUT/free_jwt_secret.txt"
printf '%s\n' 'premium-jwt-secret' > "$OUT/premium_jwt_secret.txt"
printf '%s\n' 'free-demo-key' > "$OUT/free_api_key.txt"
printf '%s\n' 'premium-demo-key' > "$OUT/premium_api_key.txt"

OPENSSL_BIN="${OPENSSL_BIN:-}"
if [[ "$OPENSSL_BIN" == [A-Za-z]:* ]]; then
  OPENSSL_BIN="$(cygpath -u "$OPENSSL_BIN" 2>/dev/null || printf '%s' "$OPENSSL_BIN")"
fi
if [ -z "$OPENSSL_BIN" ]; then
  for candidate in "/c/Program Files/OpenSSL-Win64/bin/openssl.exe" "$(command -v openssl 2>/dev/null || true)"; do
    if [ -n "$candidate" ] && [ -x "$candidate" ]; then
      OPENSSL_BIN="$candidate"
      break
    fi
  done
fi
if [ -z "$OPENSSL_BIN" ] || [ ! -x "$OPENSSL_BIN" ]; then
  echo "openssl not found; set OPENSSL_BIN to C:\\Program Files\\OpenSSL-Win64\\bin\\openssl.exe" >&2
  exit 1
fi
OUT_WIN="$(cygpath -w "$OUT" 2>/dev/null || echo "$OUT")"
"$OPENSSL_BIN" genrsa -out "$OUT_WIN/demo_rsa_private.pem" 2048 2>/dev/null
"$OPENSSL_BIN" rsa -in "$OUT_WIN/demo_rsa_private.pem" -pubout -out "$OUT_WIN/demo_rsa_public.pem" 2>/dev/null

echo "demo secrets written to $OUT"
