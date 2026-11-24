"""Fast regression tests for the CI pipeline's offline guards."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

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
        "leaky": leaky_bucket(5, 0.8, DISTINCT_TRACE),
    }
    assert len({tuple(values) for values in patterns.values()}) == 4


def test_fragment_lab_does_not_merge_yaml() -> None:
    source = (ROOT / "scripts" / "fragment_lab.py").read_text(encoding="utf-8")
    assert "import yaml" not in source
    assert "def build(" not in source
    assert "def _sections(" not in source
    assert "def parse() -> int:" in source


def test_explicit_merge_uses_no_yaml_library() -> None:
    source = (ROOT / "scripts" / "verify_fragments.py").read_text(encoding="utf-8")
    assert "import yaml" not in source
    assert "def explicit_merge(" in source
    assert "kong/kong.yml" in source


def test_live_kong_config_has_no_duplicate_top_level_keys() -> None:
    text = (ROOT / "kong" / "kong.yml").read_text(encoding="utf-8")
    keys = [
        line.split(":", 1)[0].strip()
        for line in text.splitlines()
        if line and not line[0].isspace() and not line.lstrip().startswith("#") and ":" in line
    ]
    assert len(keys) == len(set(keys)), keys


def test_live_kong_config_contains_layer2_plugins() -> None:
    text = (ROOT / "kong" / "kong.yml").read_text(encoding="utf-8")
    required = [
        "name: key-auth",
        "name: jwt",
        "name: rate-limiting",
        "name: token-bucket",
        "name: correlation-id",
        "name: request-transformer",
        "name: cors",
        "name: request-size-limiting",
        "name: prometheus",
        "name: file-log",
        "certificates:",
        "snis:",
    ]
    missing = [item for item in required if item not in text]
    assert not missing, missing
