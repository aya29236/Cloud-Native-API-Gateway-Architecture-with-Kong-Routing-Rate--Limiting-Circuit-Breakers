#!/usr/bin/env python3
"""G4 live parity check: simulator accept pattern == Kong plugin pattern.

Start the lab first (see README "G4 runbook"), then:
  python tests/fragments/verify_token_bucket.py --url http://127.0.0.1:18400
"""

from __future__ import annotations

import argparse
import http.client
import importlib.util
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent.parent


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def make_connection(url: str) -> tuple[http.client.HTTPConnection, str]:
    parsed = urlparse(url)
    return http.client.HTTPConnection(parsed.hostname, parsed.port or 80, timeout=5), parsed.path.rstrip("/")


def status(conn: http.client.HTTPConnection, path: str, token: str) -> int:
    # One persistent connection keeps the burst close to the simulator's
    # zero-gap trace; spawning curl per request would allow a token to refill.
    conn.request("GET", path + "/api/payments/health", headers={"Authorization": f"Bearer {token}"})
    response = conn.getresponse()
    response.read()
    return response.status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:18400")
    parser.add_argument("--count", type=int, default=12)
    args = parser.parse_args()

    sim = load_module("sim", ROOT / "scripts" / "token_bucket_sim.py")
    jwt = load_module("jwtgen", ROOT / "scripts" / "make_jwt.py")
    expected = sim.token_bucket(5, 1, [0.0] * args.count)
    conn, path = make_connection(args.url)
    free_token = jwt.make_jwt("fintech-free", jwt.SECRETS["fintech-free"])

    # A freshly started Kong worker can report a time cached at boot;
    # exercising the plugin-free mock route first refreshes the worker timers.
    for _ in range(3):
        conn.request("GET", path + "/mock/health")
        conn.getresponse().read()
    time.sleep(0.2)

    observed = [1 if status(conn, path, free_token) == 200 else 0 for _ in range(args.count)]
    print(f"simulator: {''.join(map(str, expected))}")
    print(f"live Kong: {''.join(map(str, observed))}")
    ok = expected == observed
    print(f"burst parity: {'PASS' if ok else 'FAIL'}")

    time.sleep(1.2)
    after_refill = status(conn, path, free_token)
    refill_ok = after_refill == 200
    print(f"after 1.2 s refill: HTTP {after_refill} ({'PASS' if refill_ok else 'FAIL'})")

    conn2, path2 = make_connection(args.url)
    premium = jwt.make_jwt("fintech-premium", jwt.SECRETS["fintech-premium"])
    premium_codes = [status(conn2, path2, premium) for _ in range(12)]
    premium_ok = all(code == 200 for code in premium_codes)
    print(f"premium 12 requests: {premium_codes} ({'PASS' if premium_ok else 'FAIL'})")
    return 0 if ok and refill_ok and premium_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
