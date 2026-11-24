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

if ! command -v openssl >/dev/null 2>&1; then
  echo "openssl not found; add real OpenSSL (Git for Windows usr/bin) to PATH" >&2
  exit 1
fi
openssl genrsa -out "$OUT/demo_rsa_private.pem" 2048 2>/dev/null
openssl rsa -in "$OUT/demo_rsa_private.pem" -pubout -out "$OUT/demo_rsa_public.pem" 2>/dev/null

echo "demo secrets written to $OUT"
