import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
RATE_LIMIT_PATH = ROOT / "kong" / "fragments" / "20-ratelimit.yml"
TRANSFORM_PATH = ROOT / "kong" / "fragments" / "30-transform.yml"


def _load_fragment(path):
    with path.open(encoding="utf-8") as fragment_file:
        fragment = yaml.safe_load(fragment_file)
    assert isinstance(fragment, dict)
    assert "_format_version" not in fragment
    assert list(fragment) == ["plugins"]
    assert isinstance(fragment["plugins"], list)
    return fragment["plugins"]


def _plugins_by_name(plugins):
    return {plugin["name"]: plugin for plugin in plugins}


def test_rate_limit_fragment_has_consumer_limits_and_headers():
    plugins = _load_fragment(RATE_LIMIT_PATH)
    assert [plugin["name"] for plugin in plugins] == [
        "rate-limiting",
        "rate-limiting",
    ]
    by_consumer = {
        plugin["consumer"]: plugin
        for plugin in plugins
    }
    assert set(by_consumer) == {"fintech-free", "fintech-premium"}

    free = by_consumer["fintech-free"]["config"]
    premium = by_consumer["fintech-premium"]["config"]
    assert free["minute"] == 10
    assert premium["minute"] == 100
    assert free["minute"] < premium["minute"]
    for config in (free, premium):
        assert config["limit_by"] == "consumer"
        assert config["policy"] == "local"
        assert config["hide_client_headers"] is False


def test_transform_fragment_has_expected_plugin_options():
    plugins = _load_fragment(TRANSFORM_PATH)
    by_name = _plugins_by_name(plugins)
    assert set(by_name) == {
        "correlation-id",
        "request-transformer",
        "cors",
        "request-size-limiting",
    }
    assert all(plugin["route"] == "mock-route" for plugin in plugins)

    correlation = by_name["correlation-id"]["config"]
    assert correlation == {
        "header_name": "Kong-Request-ID",
        "generator": "uuid",
        "echo_downstream": True,
    }
    transformer = by_name["request-transformer"]["config"]
    assert transformer["add"]["headers"] == [
        "X-Gateway: fintech-api-gateway"
    ]
    assert transformer["remove"]["headers"] == ["X-Debug"]

    cors = by_name["cors"]["config"]
    assert cors["origins"] == ["http://localhost:3000"]
    assert "OPTIONS" in cors["methods"]
    assert cors["preflight_continue"] is False
    assert "X-API-Key" in cors["headers"]
    assert "Kong-Request-ID" in cors["exposed_headers"]
    assert "X-RateLimit-Limit-Minute" in cors["exposed_headers"]
    assert "X-RateLimit-Remaining-Minute" in cors["exposed_headers"]
    assert "Retry-After" in cors["exposed_headers"]

    size_limit = by_name["request-size-limiting"]["config"]
    assert size_limit == {
        "allowed_payload_size": 1,
        "size_unit": "megabytes",
    }


def test_parser_scripts_use_kong_30_and_env_example_image():
    assert "KONG_IMAGE=kong:3.9.1" in (ROOT / ".env.example").read_text(
        encoding="utf-8"
    )
    for relative_path in (
        "scripts/kong_parse_fragments.ps1",
        "scripts/kong_parse_fragments.sh",
    ):
        script = (ROOT / relative_path).read_text(encoding="utf-8")
        assert '_format_version: "3.0"' in script
        assert ".env.example" in script
        assert "kong config parse" in script


def _docker_daemon_available():
    if shutil.which("docker") is None:
        return False
    try:
        result = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


@pytest.mark.skipif(
    not _docker_daemon_available(),
    reason="Docker CLI or daemon is unavailable",
)
def test_kong_391_parses_both_fragments():
    if os.name == "nt":
        powershell = shutil.which("pwsh") or shutil.which("powershell")
        if powershell is None:
            pytest.skip("PowerShell is unavailable")
        command = [
            powershell,
            "-NoProfile",
            "-File",
            str(ROOT / "scripts" / "kong_parse_fragments.ps1"),
        ]
    else:
        command = ["sh", str(ROOT / "scripts" / "kong_parse_fragments.sh")]

    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
