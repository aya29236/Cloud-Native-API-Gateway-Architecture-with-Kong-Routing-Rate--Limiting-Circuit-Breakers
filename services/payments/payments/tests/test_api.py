"""V2.3 contract tests against the frozen C1 Payments contract."""

import socket

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from payments.models import Payment

PAYMENT_FIELDS = {
    "id",
    "account_id",
    "amount",
    "currency",
    "status",
    "consumer",
    "created_at",
}
VALID_PAYMENT = {"account_id": 1, "amount": "49.90", "currency": "TND"}
PREMIUM = {"X-Consumer-Username": "fintech-premium"}


@pytest.mark.django_db
def test_router_urls_match_c1_paths():
    assert reverse("payment-list") == "/"
    assert reverse("payment-detail", args=[7]) == "/7"


@pytest.mark.django_db
def test_list_payments_returns_200():
    response = APIClient().get("/")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.django_db
def test_create_payment_returns_201_with_exact_c1_shape_and_consumer():
    response = APIClient().post("/", VALID_PAYMENT, format="json", headers=PREMIUM)

    assert response.status_code == 201
    body = response.json()
    assert set(body) == PAYMENT_FIELDS
    assert body["account_id"] == 1
    assert body["amount"] == "49.90"
    assert body["currency"] == "TND"
    assert body["status"] == "pending"
    assert body["consumer"] == "fintech-premium"
    assert isinstance(body["id"], int)
    assert body["created_at"].endswith("Z")


@pytest.mark.django_db
def test_consumer_is_stored_per_request():
    APIClient().post(
        "/", VALID_PAYMENT, format="json", headers={"X-Consumer-Username": "alice"}
    )
    APIClient().post(
        "/", VALID_PAYMENT, format="json", headers={"X-Consumer-Username": "bob"}
    )

    assert Payment.objects.filter(consumer="alice").count() == 1
    assert Payment.objects.filter(consumer="bob").count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    "payload",
    [
        {"amount": "1.00", "currency": "TND"},                  # account_id required
        {"account_id": 1, "currency": "TND"},                   # amount required
        {"account_id": 1, "amount": "1.00"},                    # currency required
        {**VALID_PAYMENT, "currency": "TN"},                    # 3 chars exactly
        {**VALID_PAYMENT, "unexpected": "value"},               # additionalProperties false
        {**VALID_PAYMENT, "status": "completed"},               # server-owned
        {**VALID_PAYMENT, "consumer": "fintech-premium"},       # server-owned
    ],
)
def test_create_rejects_contract_violations(payload):
    response = APIClient().post("/", payload, format="json", headers=PREMIUM)

    assert response.status_code == 400


@pytest.mark.django_db
def test_retrieve_payment_and_404_for_unknown_id():
    created = APIClient().post("/", VALID_PAYMENT, format="json", headers=PREMIUM).json()

    found = APIClient().get(f"/{created['id']}")
    missing = APIClient().get("/999999")

    assert found.status_code == 200
    assert set(found.json()) == PAYMENT_FIELDS
    assert found.json()["consumer"] == "fintech-premium"
    assert missing.status_code == 404


@pytest.mark.django_db
def test_methods_not_in_c1_are_not_available():
    created = APIClient().post("/", VALID_PAYMENT, format="json", headers=PREMIUM).json()

    assert APIClient().delete(f"/{created['id']}").status_code == 405
    assert APIClient().patch(f"/{created['id']}", {"amount": "1"}, format="json").status_code == 405


@pytest.mark.django_db
def test_gateway_headers_are_present_on_payment_responses():
    response = APIClient().get(
        "/",
        headers={
            "Kong-Request-ID": "pay-c1-1",
            "X-Consumer-Username": "fintech-premium",
        },
    )

    assert response.status_code == 200
    assert response.headers["X-Served-By"] == socket.gethostname()
    assert response.headers["Kong-Request-ID"] == "pay-c1-1"
    assert response.headers["X-Consumer-Username"] == "fintech-premium"
