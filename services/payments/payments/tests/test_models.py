"""V2.2 checks: Payment ORM behavior and C1 field semantics."""

from decimal import Decimal

import pytest

from payments.models import Payment


@pytest.mark.django_db
def test_create_and_retrieve_with_default_manager():
    created = Payment.objects.create(
        account_id=1,
        amount=Decimal("49.90"),
        currency="TND",
        consumer="fintech-premium",
    )

    fetched = Payment.objects.get(pk=created.pk)

    assert fetched.account_id == 1
    assert fetched.amount == Decimal("49.90")
    assert fetched.currency == "TND"
    assert fetched.status == Payment.STATUS_PENDING
    assert fetched.consumer == "fintech-premium"
    assert fetched.created_at is not None


@pytest.mark.django_db
def test_queryset_filter_by_consumer_and_status_is_chainable():
    Payment.objects.create(account_id=1, amount=10, currency="TND", consumer="alice")
    Payment.objects.create(account_id=1, amount=20, currency="TND", consumer="alice")
    Payment.objects.create(
        account_id=2,
        amount=30,
        currency="TND",
        consumer="bob",
        status=Payment.STATUS_COMPLETED,
    )

    alice_pending = Payment.objects.filter(consumer="alice").filter(
        status=Payment.STATUS_PENDING
    ).order_by("-amount")

    assert [p.amount for p in alice_pending] == [Decimal("20.00"), Decimal("10.00")]
    assert Payment.objects.filter(consumer="bob").count() == 1


@pytest.mark.django_db
def test_status_choices_and_string_representation():
    payment = Payment.objects.create(
        account_id=7,
        amount=Decimal("5.00"),
        currency="USD",
        consumer="fintech-free",
        status=Payment.STATUS_COMPLETED,
    )

    assert [value for value, _label in Payment.STATUS_CHOICES] == [
        "pending",
        "completed",
        "failed",
    ]
    assert str(payment).startswith(f"Payment #{payment.id} account=7 5.00 USD")
    assert "(completed)" in str(payment)
