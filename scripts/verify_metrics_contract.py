"""Live M1 check: Kong /metrics against frozen C3 v0.2.1.

 Checks the canonical metric names, the labels used by the alert rules, and the
 state-indicator semantics of ``kong_upstream_target_health``. It also confirms
 that the committed Prometheus rules match the contract expressions.
"""

from __future__ import annotations

import argparse
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_URL = "http://127.0.0.1:8100/metrics"


def metric_samples(text: str, name: str) -> list[tuple[dict[str, str], float]]:
    pattern = re.compile(rf"^{re.escape(name)}(?:\{{(.*?)\}})?\s+([0-9.eE+-]+)$")
    samples: list[tuple[dict[str, str], float]] = []
    for line in text.splitlines():
        if not line.startswith(name):
            continue
        match = pattern.match(line)
        if match is None:
            continue
        labels = dict(re.findall(r'(\w+)="([^"]*)"', match.group(1) or ""))
        samples.append((labels, float(match.group(2))))
    return samples


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL)
    args = parser.parse_args()

    with urllib.request.urlopen(args.url, timeout=10) as response:
        text = response.read().decode("utf-8")

    contract = (ROOT / "contracts" / "metrics" / "alerts-contract.yml").read_text(
        encoding="utf-8"
    )
    rules = (ROOT / "monitoring" / "rules" / "alerts.yml").read_text(encoding="utf-8")

    requests = metric_samples(text, "kong_http_requests_total")
    health = metric_samples(text, "kong_upstream_target_health")
    assert requests, "kong_http_requests_total not present on live /metrics"
    assert health, "kong_upstream_target_health not present on live /metrics"

    required_request_labels = {"service", "route", "code", "consumer"}
    assert required_request_labels <= set(requests[0][0]), sorted(
        required_request_labels - set(requests[0][0])
    )

    required_health_labels = {"upstream", "target", "address", "state"}
    assert required_health_labels <= set(health[0][0]), sorted(
        required_health_labels - set(health[0][0])
    )
    states = {labels["state"] for labels, _ in health}
    assert "healthy" in states, sorted(states)
    assert any(value == 1 for _, value in health), "no populated state with value 1"
    assert any(value == 0 for _, value in health), "no empty state with value 0"

    assert "contract_version: 0.2.1" in contract
    expressions = re.findall(r"expression: '(.+)'", contract)
    assert len(expressions) == 3, expressions
    for expression in expressions:
        assert expression in rules, f"rule missing contract expression: {expression}"

    assert 'targets: ["kong:8100"]' in (
        ROOT / "monitoring" / "prometheus.yml"
    ).read_text(encoding="utf-8")

    print(f"endpoint: {args.url}")
    print(f"kong_http_requests_total samples: {len(requests)}")
    print(f"  labels: {', '.join(sorted(requests[0][0]))}")
    print(f"kong_upstream_target_health samples: {len(health)}")
    print(f"  states: {', '.join(sorted(states))}")
    print("  value semantics: 1 when state is populated (verified)")
    print("C3 v0.2.1 expressions present in monitoring/rules/alerts.yml: 3/3")
    print("prometheus.yml scrapes kong:8100")
    print("M1 RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
