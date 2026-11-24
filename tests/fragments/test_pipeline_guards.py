"""Fast regression tests for the CI pipeline's offline guards."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from scripts.fragment_lab import build  # noqa: E402
from scripts.token_bucket_sim import (  # noqa: E402
    fixed_window,
    leaky_bucket,
    sliding_window,
    token_bucket,
)

TRACE = [0.0] * 12
DISTINCT_TRACE = [i * 0.1 for i in range(12)]


def test_token_bucket_matches_free_tier_burst_pattern() -> None:
    assert token_bucket(5, 1, TRACE) == [1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0]


def test_token_bucket_refills_after_one_second() -> None:
    trace = [0.0] * 6 + [1.0]
    assert token_bucket(5, 1, trace)[-1] == 1


def test_four_algorithms_are_distinct_on_the_same_trace() -> None:
    patterns = {
        "fixed": fixed_window(5, 0.8, DISTINCT_TRACE),
        "sliding": sliding_window(5, 0.8, DISTINCT_TRACE),
        "token": token_bucket(5, 1, DISTINCT_TRACE),
        "leaky": leaky_bucket(5, 1, DISTINCT_TRACE),
    }
    assert len({tuple(values) for values in patterns.values()}) == 4


def test_fragment_merge_has_one_header_per_top_level_section() -> None:
    target = build(
        [
            "kong/fragments/10-auth.yml",
            "kong/fragments/20-ratelimit.yml",
            "kong/fragments/25-tokenbucket.yml",
            "kong/fragments/30-transform.yml",
            "kong/fragments/40-telemetry.yml",
            "kong/fragments/50-tls.yml",
        ]
    )
    lines = target.read_text(encoding="utf-8").splitlines()

    assert sum(line.startswith("plugins:") for line in lines) == 1
    assert sum(line.startswith("consumers:") for line in lines) == 1
    assert sum(line.startswith("certificates:") for line in lines) == 1
    assert any("name: token-bucket" in line for line in lines)
    assert any("name: key-auth" in line for line in lines)
