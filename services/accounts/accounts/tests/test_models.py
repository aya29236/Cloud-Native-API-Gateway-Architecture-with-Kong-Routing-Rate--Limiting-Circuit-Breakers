"""V1.4 contract checks: Django ORM patterns from the professor's lesson.

These tests exercise the four ideas introduced at V1.4:
  1. a model class maps to one table;
  2. `objects` is the manager where every query starts;
  3. QuerySets are lazy and chainable (filter + order_by);
  4. `auto_now_add` and `DecimalField` behave as declared.
"""

from decimal import Decimal

import pytest

from accounts.models import Account


@pytest.mark.django_db
def test_create_and_retrieve_with_default_manager():
    created = Account.objects.create(owner="Alice", balance=Decimal("125.50"))

    fetched = Account.objects.get(pk=created.pk)

    assert fetched.owner == "Alice"
    assert fetched.balance == Decimal("125.50")
    assert fetched.currency == "TND"
    assert fetched.created_at is not None


@pytest.mark.django_db
def test_queryset_is_lazy_and_chainable():
    Account.objects.create(owner="Alice", balance=Decimal("100.00"))
    Account.objects.create(owner="Bob", balance=Decimal("300.00"))
    Account.objects.create(owner="Alice", balance=Decimal("200.00"))

    alice_accounts = Account.objects.filter(owner="Alice").order_by("-balance")

    # Nothing was evaluated until the list was consumed.
    assert [a.balance for a in alice_accounts] == [
        Decimal("200.00"),
        Decimal("100.00"),
    ]
    assert Account.objects.count() == 3


@pytest.mark.django_db
def test_string_representation_is_readable():
    account = Account.objects.create(owner="Carol", balance=Decimal("42.00"), currency="USD")

    assert str(account) == "Carol (42.00 USD)"
