"""V3.1 contract tests against C1's Advisor endpoints."""

import socket

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

ANALYZE_RESPONSE_FIELDS = {"summary", "stats", "citations", "tool_trace", "verified"}


def test_swagger_ui_is_served():
    response = client.get("/docs")

    assert response.status_code == 200
    assert "swagger-ui" in response.text.lower()


def test_health_returns_exact_c1_shape():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_analyze_returns_safe_no_verified_data_without_a_log_source(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("ADVISOR_LOG_PATH", str(tmp_path / "missing-access.json"))
    response = client.post("/analyze", json={"question": "Why were there 429s?"})

    assert response.status_code == 200
    body = response.json()
    assert set(body) == ANALYZE_RESPONSE_FIELDS
    assert body["summary"] == "No verified data"
    assert body["verified"] is False
    assert body["stats"] == {}
    assert body["citations"] == []
    assert [entry["tool"] for entry in body["tool_trace"]] == [
        "read_logs",
        "verify_answer",
    ]


@pytest.mark.parametrize(
    "payload",
    [
        {},                                        # question required
        {"question": ""},                          # minLength 1
        {"question": "why?", "extra": "value"},    # additionalProperties false
    ],
)
def test_analyze_rejects_contract_violations_with_400(payload):
    response = client.post("/analyze", json=payload)

    assert response.status_code == 400


def test_stats_overview_and_named_stat():
    overview = client.get("/stats")
    named = client.get("/stats/requests_total")
    missing = client.get("/stats/does_not_exist")

    assert overview.status_code == 200
    assert isinstance(overview.json(), dict)
    assert named.status_code == 200
    assert named.json() == {"requests_total": 0}
    assert missing.status_code == 404


def test_gateway_headers_are_echoed_on_all_routes():
    headers = {
        "Kong-Request-ID": "advisor-req-1",
        "X-Consumer-Username": "fintech-premium",
    }

    for method, path in [
        ("get", "/health"),
        ("get", "/stats"),
        ("post", "/analyze"),
    ]:
        kwargs = {"json": {"question": "why?"}} if method == "post" else {}
        response = getattr(client, method)(path, headers=headers, **kwargs)

        assert response.headers["X-Served-By"] == socket.gethostname()
        assert response.headers["Kong-Request-ID"] == "advisor-req-1"
        assert response.headers["X-Consumer-Username"] == "fintech-premium"
