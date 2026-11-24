"""V2.1 checks: health response and gateway headers."""

import logging
import socket

from rest_framework.test import APIClient


def test_health_returns_200_and_healthy_status():
    response = APIClient().get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_health_response_identifies_the_serving_replica():
    response = APIClient().get("/health")

    assert response.headers["X-Served-By"] == socket.gethostname()


def test_kong_request_id_is_echoed():
    response = APIClient().get("/health", headers={"Kong-Request-ID": "pay-req-1"})

    assert response.headers["Kong-Request-ID"] == "pay-req-1"


def test_consumer_username_is_echoed():
    response = APIClient().get(
        "/health", headers={"X-Consumer-Username": "fintech-premium"}
    )

    assert response.headers["X-Consumer-Username"] == "fintech-premium"


def test_each_request_is_logged_with_correlation_data(caplog):
    with caplog.at_level(logging.INFO, logger="payments.gateway"):
        APIClient().get(
            "/health",
            headers={
                "Kong-Request-ID": "pay-req-log",
                "X-Consumer-Username": "fintech-free",
            },
        )

    messages = [r.getMessage() for r in caplog.records if r.name == "payments.gateway"]
    assert len(messages) == 1
    assert "request_id=pay-req-log" in messages[0]
    assert "consumer=fintech-free" in messages[0]
    assert "status=200" in messages[0]
