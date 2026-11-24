#!/usr/bin/env python3
"""Final Gate audit for the Kong FinTech prototype.

Uses only the Python standard library. It checks the frozen contracts, the
live Kong/PostgreSQL/Compose topology, C1-C4 behaviour, evidence artifacts,
CI structure and repository invariants, then prints one grouped result per
gate. Open items are reported as WARN, not silently marked complete.
"""

from __future__ import annotations

import json
import re
import ssl
import struct
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
PROXY = "http://127.0.0.1:8000"
ADMIN = "http://127.0.0.1:8001"
PROMETHEUS = "http://127.0.0.1:9090"
KEY_HEADERS = {"apikey": "premium-demo-key"}
CONTEXT = ssl._create_unverified_context()

RESULTS: dict[str, list[tuple[str, bool, str]]] = {}
WARNINGS: list[str] = []


def add(gate: str, name: str, ok: bool, detail: str = "") -> None:
    RESULTS.setdefault(gate, []).append((name, bool(ok), detail))


def warn(message: str) -> None:
    if message not in WARNINGS:
        WARNINGS.append(message)


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def request(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    timeout: int = 8,
) -> tuple[int, dict[str, str], bytes]:
    req = urllib.request.Request(url, data=body, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CONTEXT) as response:
            return response.status, dict(response.headers.items()), response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers.items()), exc.read()


def json_get(url: str) -> Any:
    _, _, body = request(url)
    return json.loads(body)


def jwt_token() -> str:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "make_jwt.py"), "--iss", "fintech-free"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return next(line for line in reversed(lines) if line.count(".") == 2)


def analyze(question: str) -> dict[str, Any]:
    body = json.dumps({"question": question}).encode("utf-8")
    _, _, raw = request(
        f"{PROXY}/api/advisor/analyze",
        method="POST",
        headers={**KEY_HEADERS, "Content-Type": "application/json"},
        body=body,
        timeout=20,
    )
    return json.loads(raw)


def check_contracts() -> None:
    gate = "C1-C4 contracts"
    c1 = text("contracts/api/openapi.yml")
    c2 = text("contracts/logs/kong-access-log.schema.json")
    c3 = text("contracts/metrics/alerts-contract.yml")
    c4 = text("contracts/naming/environment.yml")
    add(gate, "C1 version", "version: 0.3.0" in c1)
    add(gate, "C2 version/frozen", '"contract_version": "0.1.1"' in c2 and '"frozen": true' in c2)
    add(gate, "C3 version", "contract_version: 0.2.1" in c3)
    add(gate, "C4 version", "contract_version: 0.2.1" in c4)
    add(gate, "approvals", all("Wafe Bziouiche" in value for value in (c1, c3, c4)))
    readme = text("README.md")
    add(
        gate,
        "DB-less vs Postgres theory",
        all(
            marker in readme
            for marker in (
                "## Kong deployment modes — theory overview",
                "DB-less declarative mode (implemented)",
                "PostgreSQL mode (theory only)",
                "kong migrations bootstrap",
                "kong config db_import",
            )
        )
        and "dbmode_lab" not in c4,
    )


def check_topology() -> None:
    gate = "Kong topology"
    kong = text("kong/kong.yml")
    add(gate, "version/transform", '_format_version: "3.0"' in kong and "_transform: true" in kong)
    add(gate, "services/routes", all(f"name: {name}" in kong for name in ("accounts", "payments", "advisor")))
    add(gate, "mock route", "/mock" in kong and "mock-upstream" in kong)
    add(gate, "healthchecks", kong.count("healthchecks:") == 3)
    add(gate, "active/passive", kong.count("active:") == 3 and kong.count("passive:") == 3)
    add(gate, "429 excluded", all("429" not in line for line in kong.splitlines() if "http_statuses:" in line))
    status, _, _ = request(f"{ADMIN}/services")
    add(gate, "admin read", status == 200)
    status, _, _ = request(f"{ADMIN}/services/mock-upstream", method="DELETE")
    add(gate, "admin read-only", status == 405)
    health = json_get(f"{ADMIN}/upstreams/accounts-upstream/health")
    states = [target.get("health") for target in health.get("data", [])]
    add(gate, "targets healthy", len(states) == 2 and all(state == "HEALTHY" for state in states), ",".join(map(str, states)))


def check_c1() -> None:
    gate = "C1 routes/auth"
    for route in ("accounts", "advisor"):
        status, headers, _ = request(f"{PROXY}/api/{route}/health", headers=KEY_HEADERS)
        add(
            gate,
            f"{route} key-auth",
            status == 200
            and bool(headers.get("X-Served-By") or headers.get("x-served-by"))
            and bool(headers.get("Kong-Request-ID") or headers.get("kong-request-id")),
            f"HTTP {status}",
        )
    status, headers, _ = request(
        f"{PROXY}/api/payments/health", headers={"Authorization": f"Bearer {jwt_token()}"}
    )
    add(
        gate,
        "payments JWT",
        status == 200 and bool(headers.get("Kong-Request-ID") or headers.get("kong-request-id")),
        f"HTTP {status}",
    )
    status, _, _ = request(f"{PROXY}/api/accounts/health")
    add(gate, "missing key rejected", status == 401, f"HTTP {status}")
    status, _, _ = request(f"{PROXY}/api/payments/health", headers=KEY_HEADERS)
    add(gate, "wrong payments auth rejected", status == 401, f"HTTP {status}")
    status, _, _ = request("https://localhost:8443/api/accounts/health", headers=KEY_HEADERS)
    add(gate, "TLS proxy", status == 200, f"HTTP {status}")
    expected = {"/mock/health": 200, "/mock/echo": 200, "/mock/fail": 500, "/mock/slow": 200}
    for path, code in expected.items():
        status, _, _ = request(f"{PROXY}{path}")
        add(gate, f"mock {path}", status == code, f"HTTP {status}")


def check_c2() -> None:
    gate = "C2 access log"
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "kong", "sh", "-c", "tail -n 1 /var/log/kong/access.json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    record = json.loads(result.stdout.strip())
    required = {"client_ip", "request", "response", "latencies", "started_at"}
    add(gate, "required fields", required <= set(record))
    add(gate, "request fields", {"method", "uri"} <= set(record.get("request", {})))
    add(gate, "response/latency fields", "status" in record.get("response", {}) and "proxy" in record.get("latencies", {}))
    add(gate, "fixture valid", json.loads(text("fixtures/access.json")) is not None)


def check_c3() -> None:
    gate = "C3 metrics/alerts"
    targets = json_get(f"{PROMETHEUS}/api/v1/targets")
    kong_targets = [item for item in targets.get("data", {}).get("activeTargets", []) if item.get("labels", {}).get("job") == "kong"]
    add(gate, "kong scrape up", any(item.get("health") == "up" for item in kong_targets))
    rules = json_get(f"{PROMETHEUS}/api/v1/rules")
    rule_count = sum(len(group.get("rules", [])) for group in rules.get("data", {}).get("groups", []))
    add(gate, "3 alert rules loaded", rule_count == 3, f"rules={rule_count}")
    ams = json_get(f"{PROMETHEUS}/api/v1/alertmanagers")
    urls = ",".join(item.get("url", "") for item in ams.get("data", {}).get("activeAlertmanagers", []))
    add(gate, "Alertmanager connected", "alertmanager:9093" in urls)
    contract = text("contracts/metrics/alerts-contract.yml")
    add(gate, "alert names", all(name in contract for name in ("KongCircuitOpen", "Kong429Spike", "KongUpstreamTargetUnhealthy")))
    add(gate, "workflow files", all((ROOT / f"n8n/workflows/{name}").is_file() for name in ("00-alert-router.json", "10-circuit-open.json", "20-429-spike.json")))
    add(gate, "n8n verifier", subprocess.run([sys.executable, "n8n/workflows/validate.py"], cwd=ROOT, capture_output=True).returncode == 0)


def check_c4() -> None:
    gate = "C4 compose/load"
    compose = text("docker-compose.yml")
    add(gate, "profiles", all(f'profiles: ["{name}"]' in compose for name in ("core", "monitoring", "load", "ai")))
    add(gate, "postgres 16", "postgres:16" in compose and "127.0.0.1:5433:5432" in compose)
    add(gate, "replicas", all(name in compose for name in ("accounts-1", "accounts-2", "payments-1", "payments-2", "advisor-1", "advisor-2")))
    add(gate, "k6 + Locust", "grafana/k6:1.8.0" in compose and "locustio/locust:2.47.0" in compose)
    add(gate, "Django runserver", "runserver" in text("services/accounts/Dockerfile") and "runserver" in text("services/payments/Dockerfile"))
    add(gate, "no PyYAML merge", "import yaml" not in text("scripts/fragment_lab.py") and "import yaml" not in text("scripts/verify_fragments.py"))
    add(gate, "CI green gate", all(name in text(".github/workflows/ci.yml") for name in ("P3a repository checks", "P3b pytest + Kong parse + plugin mocks", "P3c platform gates + image builds", "CI green gate")))


def check_analyzer() -> None:
    gate = "Layer 5 analyzer"
    source = text("advisor/app/analyzer.py")
    add(gate, "tool loop", all(name in source for name in ("read_logs", "filter_records", "aggregate", "verify_answer")))
    add(gate, "IP stats", all(name in source for name in ("client_ip_counts", "distinct_client_ips", "top_client_ip")))
    overview = analyze("How many requests were logged?")
    add(gate, "verified overview", overview.get("verified") is True and overview.get("stats", {}).get("requests_total", 0) > 0)
    ips = analyze("Which client IPs caused errors?")
    add(gate, "verified client IPs", ips.get("verified") is True and ips.get("stats", {}).get("distinct_client_ips", 0) > 0)
    unavailable = analyze("Why were there 503s?")
    add(
        gate,
        "exact fallback",
        unavailable.get("summary") == "No verified data"
        and unavailable.get("verified") is False
        and unavailable.get("citations") == [],
    )
    _, _, raw = request(f"{PROXY}/api/advisor/stats/requests_total", headers=KEY_HEADERS)
    add(gate, "live /stats endpoint", json.loads(raw).get("requests_total", 0) > 0)


def check_evidence() -> None:
    gate = "Evidence/docs"
    names = sorted(path.name for path in (ROOT / "screenshots").glob("*.png"))
    pattern = re.compile(r"\d{2}_[A-Za-z0-9_-]+\.png")
    valid = bool(names)
    for name in names:
        data = (ROOT / "screenshots" / name).read_bytes()
        valid = valid and bool(pattern.fullmatch(name)) and data[:8] == b"\x89PNG\r\n\x1a\n"
        if valid and len(data) >= 24:
            width, height = struct.unpack(">II", data[16:24])
            valid = valid and width > 0 and height > 0
    add(gate, "PNG filenames/signatures", valid, f"count={len(names)}")
    readme = text("README.md")
    required_rows = ("01_", "02_", "03_", "18_", "19_", "20_", "21_", "22_", "23_", "24_")
    add(gate, "README evidence rows", all(name in readme for name in required_rows))
    add(gate, "decisions log", "DEC-019" in text("decisions.md"))
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    add(
        gate,
        "clean tracked secrets",
        "demo-token" in text(".env.example")
        and ".env" not in tracked
        and "kong/kong.yml.backup" not in tracked,
    )
    branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    add(gate, "branch invariant", branch == "ci/prototype-pipeline", branch)

    missing = [number for number in ("01", "02", "03", "10", "11", "13", "14", "18") if not any(name.startswith(number + "_") for name in names)]
    if missing:
        warn(f"owner evidence IDs not present in screenshots/: {', '.join(missing)} (14 blocked on Telegram)")
    readme_gate0 = readme.split("## Gate 0 status", 1)[1].split("## Continuous integration", 1)[0]
    for line in readme_gate0.splitlines():
        if line.startswith("- [ ]"):
            warn(f"Gate 0 checkbox still open: {line[6:].strip()}")


def main() -> int:
    check_contracts()
    check_topology()
    check_c1()
    check_c2()
    check_c3()
    check_c4()
    check_analyzer()
    check_evidence()

    warn("Telegram test credentials absent; real delivery evidence 14 remains blocked")
    warn("main branch protection could not be re-verified without an authenticated GitHub token")

    failures = 0
    for gate, checks in RESULTS.items():
        passed = sum(1 for _, ok, _ in checks if ok)
        ok = passed == len(checks)
        failures += 0 if ok else 1
        detail = f"{passed}/{len(checks)} checks"
        if not ok:
            detail += "; failed: " + ", ".join(name for name, result, _ in checks if not result)
        print(f"{'PASS' if ok else 'FAIL'} {gate}: {detail}")
    for message in WARNINGS:
        print(f"WARN {message}")
    verdict = "FAIL" if failures else ("PASS WITH WARNINGS" if WARNINGS else "PASS")
    print(f"FINAL GATE RESULT: {verdict}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
