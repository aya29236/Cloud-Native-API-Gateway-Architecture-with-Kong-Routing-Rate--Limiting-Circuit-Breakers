"""API views for Accounts (V1.2 health, V1.5 CRUD and fault injection)."""

import random
import time

from django.conf import settings
from rest_framework import status, viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Account
from .serializers import AccountSerializer


class AccountViewSet(viewsets.ModelViewSet):
    """Full CRUD for Account, routed by SimpleRouter in accounts/urls.py.

    The professor's lesson uses a ViewSet + router instead of hand-written
    list/detail views: one class supplies list, create, retrieve, update and
    destroy, and the router generates the URL patterns.
    """

    queryset = Account.objects.all().order_by("id")
    serializer_class = AccountSerializer


@api_view(["GET"])
def health(request):
    """
    Liveness endpoint.

    Kong active health checks call GET /health every 2-5 seconds at Layer 3.
    It must stay cheap and must not touch the database, so it can answer
    even when the ORM layer is unhealthy.
    """
    return Response({"status": "healthy"})


@api_view(["GET"])
def fail(request):
    """Controlled 500 used by passive health-check and circuit-breaker tests."""
    return Response(
        {"detail": "deliberate upstream failure"},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


@api_view(["GET"])
def slow(request):
    """Delayed 200 used for latency, timeout and resilience tests."""
    delay = settings.ACCOUNTS_SLOW_SECONDS
    time.sleep(delay)
    return Response({"status": "slow_response", "delay_seconds": delay})


@api_view(["GET"])
def flaky(request):
    """Randomly 200 or 500, used to demonstrate intermittent failures."""
    if random.random() < settings.ACCOUNTS_FLAKY_FAILURE_RATE:
        return Response(
            {"detail": "intermittent upstream failure"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    return Response({"status": "ok"})
