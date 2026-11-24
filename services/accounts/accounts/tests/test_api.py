"""V1.5 contract tests against the frozen C1 Accounts contract.

These tests intentionally fail if a C1 field, status code or header changes.
They exercise the service directly; Kong-level checks (401/429/TLS) belong
to Layer 2.
"""

import socket

import pytest
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient

ACCOUNT_FIELDS = {"id", "owner", "balance", "currency", "created_at"}
VALID_ACCOUNT = {"owner": "Alice", "balance": "125.50", "currency": "TND"}


@pytest.mark.django_db
def test_router_urls_match_c1_paths():
    assert reverse("account-list") == "/"
    assert reverse("account-detail", args=[7]) == "/7"


@pytest.mark.django_db
def test_list_accounts_returns_200_with_c1_fields():
    response = APIClient().get("/")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.django_db
def test_create_account_returns_201_with_exact_c1_shape():
    response = APIClient().post("/", VALID_ACCOUNT, format="json")

    assert response.status_code == 201
    body = response.json()
    assert set(body) == ACCOUNT_FIELDS
    assert body["owner"] == "Alice"
    assert body["balance"] == "125.50"
    assert body["currency"] == "TND"
    assert isinstance(body["id"], int)
    assert body["created_at"].endswith("Z")


@pytest.mark.django_db
@pytest.mark.parametrize(
    "payload",
    [
        {"balance": "1.00", "currency": "TND"},          # owner required
        {"owner": "Alice", "currency": "TND"},           # balance required
        {"owner": "Alice", "balance": "1.00"},           # currency required
        {**VALID_ACCOUNT, "currency": "TN"},             # minLength 3
        {**VALID_ACCOUNT, "unexpected": "value"},        # additionalProperties false
    ],
)
def test_create_rejects_contract_violations(payload):
    response = APIClient().post("/", payload, format="json")

    assert response.status_code == 400


@pytest.mark.django_db
def test_retrieve_account_and_404_for_unknown_id():
    created = APIClient().post("/", VALID_ACCOUNT, format="json").json()

    found = APIClient().get(f"/{created['id']}")
    missing = APIClient().get("/999999")

    assert found.status_code == 200
    assert set(found.json()) == ACCOUNT_FIELDS
    assert found.json()["id"] == created["id"]
    assert missing.status_code == 404


@pytest.mark.django_db
def test_gateway_headers_are_present_on_account_responses():
    response = APIClient().get(
        "/",
        headers={
            "Kong-Request-ID": "req-c1-1",
            "X-Consumer-Username": "fintech-premium",
        },
    )

    assert response.status_code == 200
    assert response.headers["X-Served-By"] == socket.gethostname()
    assert response.headers["Kong-Request-ID"] == "req-c1-1"
    assert response.headers["X-Consumer-Username"] == "fintech-premium"


def test_fail_returns_500_with_gateway_headers():
    response = APIClient().get("/fail", headers={"Kong-Request-ID": "req-fail"})

    assert response.status_code == 500
    assert response.headers["X-Served-By"] == socket.gethostname()
    assert response.headers["Kong-Request-ID"] == "req-fail"


@override_settings(ACCOUNTS_SLOW_SECONDS=0.01)
def test_slow_returns_delay_response():
    response = APIClient().get("/slow")

    assert response.status_code == 200
    assert response.json()["status"] == "slow_response"
    assert response.json()["delay_seconds"] == 0.01
    assert response.headers["X-Served-By"] == socket.gethostname()


@override_settings(ACCOUNTS_FLAKY_FAILURE_RATE=0.0)
def test_flaky_can_be_forced_to_succeed():
    response = APIClient().get("/flaky")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@override_settings(ACCOUNTS_FLAKY_FAILURE_RATE=1.0)
def test_flaky_can_be_forced_to_fail():
    response = APIClient().get("/flaky", headers={"Kong-Request-ID": "req-flaky"})

    assert response.status_code == 500
    assert response.headers["Kong-Request-ID"] == "req-flaky"
    assert response.headers["X-Served-By"] == socket.gethostname()
