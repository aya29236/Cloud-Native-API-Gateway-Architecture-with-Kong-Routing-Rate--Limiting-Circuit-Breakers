"""Layer 5 tests for the verified tool-calling analyzer."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.analyzer import NO_VERIFIED_DATA, answer_question, read_logs, verify_answer
from app.main import app

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "access.json"


def _record(status: int, *, consumer: str = "fintech-free", route: str = "accounts") -> dict:
    return {
        "client_ip": "192.168.1.10",
        "request": {"method": "GET", "uri": f"/api/{route}"},
        "response": {"status": status},
        "latencies": {"proxy": 12, "kong": 1, "request": 13},
        "started_at": 1795220000,
        "consumer": {"username": consumer},
        "route": {"name": route},
        "service": {"name": route},
    }


def test_verified_overview_uses_fixture_citations(monkeypatch):
    monkeypatch.setenv("ADVISOR_LOG_PATH", str(FIXTURE))

    result = answer_question("How many requests are in the gateway log?")

    assert result.verified is True
    assert result.summary == "Verified 1 C2-valid request(s) in the Kong access logs."
    assert result.stats["requests_total"] == 1
    assert result.stats["status_counts"] == {"200": 1}
    assert result.citations == ["[L1]"]
    assert [entry["tool"] for entry in result.tool_trace] == [
        "read_logs",
        "filter_records",
        "aggregate",
        "verify_answer",
    ]


def test_unsupported_429_question_uses_exact_c1_fallback(monkeypatch):
    monkeypatch.setenv("ADVISOR_LOG_PATH", str(FIXTURE))

    result = answer_question("Why were there 429s?")

    assert result.summary == NO_VERIFIED_DATA
    assert result.verified is False
    assert result.citations == []
    assert result.stats["requests_total"] == 1
    assert result.tool_trace[1]["arguments"]["intent"] == "rate_limit"
    assert result.tool_trace[-1]["result"] == {"verified": False}


def test_429_jsonl_log_produces_verified_answer(monkeypatch, tmp_path):
    log = tmp_path / "access.json"
    log.write_text(
        "\n".join(
            [
                json.dumps(_record(200)),
                json.dumps(_record(429, consumer="fintech-premium", route="payments")),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ADVISOR_LOG_PATH", str(log))

    result = answer_question("Why were there 429s?")

    assert result.verified is True
    assert result.summary == "Verified 1 HTTP 429 rate-limited request(s) in the Kong access logs."
    assert result.stats["rate_limited_total"] == 1
    assert result.citations == ["[L2]"]

    records, info = read_logs(str(log))
    assert info["valid_records"] == 2
    assert verify_answer(result, records, result.tool_trace) is True


def test_verifier_rejects_a_forged_citation(monkeypatch):
    monkeypatch.setenv("ADVISOR_LOG_PATH", str(FIXTURE))
    result = answer_question("overview")
    records, _ = read_logs(str(FIXTURE))

    forged = result.model_copy(update={"citations": ["[L99]"]})

    assert verify_answer(forged, records, result.tool_trace) is False


def test_invalid_c2_record_is_skipped_and_citation_id_is_stable(monkeypatch, tmp_path):
    log = tmp_path / "access.json"
    log.write_text(
        json.dumps({"client_ip": "incomplete"}) + "\n" + json.dumps(_record(200)) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ADVISOR_LOG_PATH", str(log))

    records, info = read_logs(str(log))
    result = answer_question("overview")

    assert len(records) == 1
    assert info["invalid_records"] == 1
    assert result.stats["requests_total"] == 1
    assert result.citations == ["[L2]"]


def test_stats_endpoints_read_the_same_verified_aggregate(monkeypatch):
    monkeypatch.setenv("ADVISOR_LOG_PATH", str(FIXTURE))
    client = TestClient(app)

    overview = client.get("/stats")
    named = client.get("/stats/requests_total")
    rate_limited = client.get("/stats/rate_limited_total")
    missing = client.get("/stats/not_a_stat")

    assert overview.status_code == 200
    assert overview.json()["requests_total"] == 1
    assert named.json() == {"requests_total": 1}
    assert rate_limited.json() == {"rate_limited_total": 0}
    assert missing.status_code == 404
