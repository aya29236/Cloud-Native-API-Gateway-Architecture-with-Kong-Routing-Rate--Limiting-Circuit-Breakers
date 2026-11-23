import json
from typing import Any

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from advisor.ai1.generator import generate_synthetic_logs, make_record
from advisor.ai1.reader import LogReaderResult, read_kong_log_text
from advisor.ai1.tools import (
    consumer_stats,
    get_log_lines,
    status_breakdown,
    time_range,
    top_ip_route_pairs,
    top_ips,
    top_routes,
)
from advisor.ai2.llm import ScriptedClient
from advisor.api import analyze_router, stats_router
from advisor.api.analyze import get_llm_client
from advisor.api.app import create_app
from advisor.api.stats import get_log_result, get_records


def _tool_call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {"function": {"name": name, "arguments": arguments}}
        ],
    }


def _data() -> tuple[str, list[dict[str, Any]], LogReaderResult]:
    text, raw, _expected = generate_synthetic_logs(seed=2026)
    return text, raw, read_kong_log_text(text)


def _stats_app(
    records: list[Any],
    result: LogReaderResult | None = None,
    with_analyze: bool = False,
) -> FastAPI:
    application = FastAPI()
    application.include_router(stats_router)
    if with_analyze:
        application.include_router(analyze_router)
    application.dependency_overrides[get_records] = lambda: records
    if result is not None:
        application.dependency_overrides[get_log_result] = lambda: result
    return application


def _frame(raw_records: list[dict[str, Any]], parsed_records: list[Any]) -> pd.DataFrame:
    rows = []
    for raw, parsed in zip(raw_records, parsed_records, strict=True):
        route = raw.get("route")
        consumer = raw.get("consumer")
        rows.append(
            {
                "line_number": parsed.line_number,
                "started_at": raw["started_at"],
                "status": raw["response"]["status"],
                "client_ip": raw["client_ip"],
                "route": (
                    route.get("name")
                    if route is not None and route.get("name")
                    else raw["request"]["uri"]
                ),
                "consumer": (
                    consumer.get("username")
                    if consumer is not None and consumer.get("username")
                    else "anonymous"
                ),
            }
        )
    return pd.DataFrame(rows)


def _ranked(
    frame: pd.DataFrame,
    keys: list[str],
    limit: int | None = None,
) -> list[dict[str, Any]]:
    grouped = frame.groupby(keys, dropna=False).size().reset_index(name="count")
    grouped = grouped.sort_values(
        ["count", *keys],
        ascending=[False, *([True] * len(keys))],
        kind="mergesort",
    )
    if limit is not None:
        grouped = grouped.head(limit)
    return grouped.to_dict(orient="records")


def test_stats_endpoints_match_tools_and_independent_pandas_results():
    text, raw_records, parsed = _data()
    records = parsed.records
    frame = _frame(raw_records, records)
    window = frame[
        (frame["started_at"] >= 1005) & (frame["started_at"] <= 1023)
    ]

    with TestClient(_stats_app(records, parsed)) as client:
        status = client.get("/stats/status?start_at=1005&end_at=1023").json()
        assert status == {
            str(key): value
            for key, value in status_breakdown(records, 1005, 1023).items()
        }
        pandas_status = (
            window.groupby("status").size().sort_index().astype(int).to_dict()
        )
        assert status == {str(key): value for key, value in pandas_status.items()}

        ips = client.get(
            "/stats/top-ips?limit=4&start_at=1005&end_at=1023"
        ).json()
        assert ips == top_ips(records, 4, 1005, 1023)
        assert ips == _ranked(window, ["client_ip"], limit=4)

        routes = client.get(
            "/stats/top-routes?limit=4&start_at=1005&end_at=1023"
        ).json()
        assert routes == top_routes(records, 4, 1005, 1023)
        assert routes == _ranked(window, ["route"], limit=4)

        pairs = client.get(
            "/stats/top-pairs?limit=4&start_at=1005&end_at=1023"
        ).json()
        assert pairs == top_ip_route_pairs(records, 4, 1005, 1023)
        assert pairs == _ranked(window, ["client_ip", "route"], limit=4)

        consumers = client.get(
            "/stats/consumers?start_at=1005&end_at=1023"
        ).json()
        assert consumers == consumer_stats(records, 1005, 1023)
        assert consumers == _ranked(window, ["consumer"])

        selected = frame[
            (frame["started_at"] >= 1019) & (frame["started_at"] <= 1023)
        ]
        time_result = client.get(
            "/stats/time-range?start_at=1019&end_at=1023"
        ).json()
        assert time_result == [
            item.model_dump(mode="json")
            for item in time_range(records, 1019, 1023)
        ]
        assert [item["line_number"] for item in time_result] == (
            selected["line_number"].tolist()
        )

        lines = client.get("/stats/lines?limit=100").json()
        assert lines == get_log_lines(records, 100)
        pandas_lines = frame.sort_values("line_number").head(20)["line_number"]
        assert [item["line_number"] for item in lines] == pandas_lines.tolist()

        counts = client.get("/stats/reader-counts").json()
        assert counts == {
            "valid": parsed.valid_count,
            "blank": parsed.blank_count,
            "malformed": parsed.malformed_count,
        }
        pandas_valid_count = int(len(frame))
        physical_lines = text.splitlines()
        pandas_blank_count = sum(not line.strip() for line in physical_lines)
        malformed_count = 0
        for line in physical_lines:
            if not line.strip():
                continue
            try:
                json.loads(line)
            except json.JSONDecodeError:
                malformed_count += 1
        assert counts == {
            "valid": pandas_valid_count,
            "blank": pandas_blank_count,
            "malformed": malformed_count,
        }


def test_lines_endpoint_enforces_its_own_twenty_line_cap(monkeypatch):
    import advisor.api.stats as stats_module

    records: list[Any] = []
    fake_lines = [
        {"line_id": f"L{index}", "line_number": index, "record": {}}
        for index in range(1, 36)
    ]
    monkeypatch.setattr(stats_module, "get_log_lines", lambda *_args: fake_lines)
    with TestClient(_stats_app(records)) as client:
        response = client.get("/stats/lines?limit=35")
    assert response.status_code == 200
    assert len(response.json()) == 20


def test_invalid_time_range_returns_422():
    _text, _raw, parsed = _data()
    with TestClient(_stats_app(parsed.records)) as client:
        response = client.get("/stats/time-range?start_at=2000&end_at=1000")
    assert response.status_code == 422
    assert "start_at" in response.json()["detail"]


def test_missing_log_returns_503(monkeypatch, tmp_path):
    missing = tmp_path / "missing.json"
    monkeypatch.setenv("KONG_LOG_PATH", str(missing))
    app = FastAPI()
    app.include_router(stats_router)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/stats/status")
    assert response.status_code == 503
    assert str(missing) in response.json()["detail"]


def test_file_is_read_on_each_request_and_never_modified(monkeypatch, tmp_path):
    path = tmp_path / "access.json"
    first = make_record(
        ip="192.0.2.1",
        uri="/first",
        status=200,
        started_at=1,
    )
    second = make_record(
        ip="192.0.2.2",
        uri="/second",
        status=503,
        started_at=2,
    )
    path.write_text(json.dumps(first), encoding="utf-8")
    monkeypatch.setenv("KONG_LOG_PATH", str(path))
    app = FastAPI()
    app.include_router(stats_router)

    with TestClient(app) as client:
        before = path.read_bytes()
        assert client.get("/stats/status").json() == {"200": 1}
        assert path.read_bytes() == before

        path.write_text(json.dumps(second), encoding="utf-8")
        before = path.read_bytes()
        assert client.get("/stats/status").json() == {"503": 1}
        assert path.read_bytes() == before


def test_stats_routes_are_get_only():
    _text, _raw, parsed = _data()
    with TestClient(_stats_app(parsed.records)) as client:
        response = client.post("/stats/status")
    assert response.status_code == 405


def test_analyze_returns_exact_c1_shape_and_verified_semantics(monkeypatch):
    import advisor.ai3.pipeline as pipeline

    _text, _raw, parsed = _data()
    saved_traces = []
    monkeypatch.setattr(
        pipeline,
        "save_trace",
        lambda response, extra=None: saved_traces.append((response, extra)),
    )
    client_script = ScriptedClient(
        [
            _tool_call("top_ips", {"limit": 1}),
            {"role": "assistant", "content": "198.51.100.44"},
        ]
    )
    app = _stats_app(parsed.records, with_analyze=True)
    app.dependency_overrides[get_llm_client] = lambda: client_script

    with TestClient(app) as client:
        response = client.post(
            "/analyze",
            json={"question": "Which IP has the most requests?"},
        )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"summary", "stats", "citations", "tool_trace", "verified"}
    assert body["summary"] == "198.51.100.44"
    assert body["verified"] is True
    assert len(saved_traces) == 1


def test_analyze_failed_retry_delivers_verified_refusal_and_saves_fallback(
    monkeypatch,
):
    import advisor.ai3.pipeline as pipeline

    _text, _raw, parsed = _data()
    saved_traces = []
    monkeypatch.setattr(
        pipeline,
        "save_trace",
        lambda response, extra=None: saved_traces.append((response, extra)),
    )
    scripted = ScriptedClient(
        [
            _tool_call("top_ips", {"limit": 1}),
            {"role": "assistant", "content": "192.0.2.250"},
            _tool_call("top_ips", {"limit": 1}),
            {"role": "assistant", "content": "192.0.2.251"},
        ]
    )
    app = _stats_app(parsed.records, with_analyze=True)
    app.dependency_overrides[get_llm_client] = lambda: scripted

    with TestClient(app) as client:
        response = client.post("/analyze", json={"question": "Which IP?"})

    assert response.status_code == 200
    body = response.json()
    assert body["summary"] == "No verified data"
    assert body["verified"] is True
    assert saved_traces[0][1]["fallback"] is True
    assert saved_traces[0][1]["attempt_count"] == 2
    assert len(saved_traces[0][1]["verifier_reports"]) == 2


def test_analyze_returns_503_when_model_is_unconfigured(monkeypatch):
    _text, _raw, parsed = _data()
    monkeypatch.delenv("ADVISOR_MODEL", raising=False)
    app = _stats_app(parsed.records, with_analyze=True)
    with TestClient(app) as client:
        response = client.post("/analyze", json={"question": "Which IP?"})
    assert response.status_code == 503
    assert "ADVISOR_MODEL" in response.json()["detail"]


@pytest.mark.parametrize(
    ("error", "detail_fragment"),
    [
        ("Cannot reach Ollama at http://localhost:11434/api/chat: refused", "Cannot reach Ollama"),
        (
            "Cannot reach Ollama at http://localhost:11434/api/chat: HTTP Error 404: Not Found",
            "model may not be pulled",
        ),
    ],
)
def test_analyze_returns_503_for_ollama_errors(
    monkeypatch,
    error: str,
    detail_fragment: str,
):
    import advisor.ai3.pipeline as pipeline

    class FailingClient:
        def chat(self, _messages, _tools):
            raise RuntimeError(error)

    _text, _raw, parsed = _data()
    monkeypatch.setattr(pipeline, "save_trace", lambda *_args, **_kwargs: None)
    app = _stats_app(parsed.records, with_analyze=True)
    app.dependency_overrides[get_llm_client] = FailingClient
    with TestClient(app) as client:
        response = client.post("/analyze", json={"question": "Which IP?"})
    assert response.status_code == 503
    assert detail_fragment.lower() in response.json()["detail"].lower()


def test_router_can_be_included_in_a_fresh_fastapi_shell(monkeypatch):
    import advisor.ai3.pipeline as pipeline

    _text, _raw, parsed = _data()
    monkeypatch.setattr(pipeline, "save_trace", lambda *_args, **_kwargs: None)
    scripted = ScriptedClient(
        [
            _tool_call("top_ips", {"limit": 1}),
            {"role": "assistant", "content": "198.51.100.44"},
        ]
    )
    fresh_shell = FastAPI()
    fresh_shell.include_router(stats_router)
    fresh_shell.include_router(analyze_router)
    fresh_shell.dependency_overrides[get_records] = lambda: parsed.records
    fresh_shell.dependency_overrides[get_llm_client] = lambda: scripted

    with TestClient(fresh_shell) as client:
        stats_response = client.get("/stats/status")
        analyze_response = client.post(
            "/analyze",
            json={"question": "Which IP has the most requests?"},
        )
    assert stats_response.status_code == 200
    assert analyze_response.status_code == 200
    assert analyze_response.json()["verified"] is True


def test_local_app_falls_back_to_synthetic_logs(monkeypatch):
    monkeypatch.delenv("KONG_LOG_PATH", raising=False)
    with TestClient(create_app()) as client:
        health = client.get("/health")
        top_ips_response = client.get("/stats/top-ips")
    assert health.json() == {"status": "healthy", "data_source": "synthetic"}
    assert top_ips_response.status_code == 200
    assert top_ips_response.json()[0]["client_ip"] == "198.51.100.44"


def test_local_app_falls_back_when_configured_log_is_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("KONG_LOG_PATH", str(tmp_path / "missing.jsonl"))
    with TestClient(create_app()) as client:
        health = client.get("/health")
        status = client.get("/stats/status")
    assert health.json()["data_source"] == "synthetic"
    assert status.json() == {"200": 12, "429": 8, "503": 5}


def test_local_app_uses_an_existing_configured_kong_log(monkeypatch, tmp_path):
    path = tmp_path / "kong-access.json"
    path.write_text(
        json.dumps(
            make_record(
                ip="192.0.2.9",
                uri="/configured",
                status=201,
                started_at=9,
            )
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("KONG_LOG_PATH", str(path))
    with TestClient(create_app()) as client:
        health = client.get("/health")
        status = client.get("/stats/status")
    assert health.json()["data_source"] == "kong-log"
    assert status.json() == {"201": 1}
