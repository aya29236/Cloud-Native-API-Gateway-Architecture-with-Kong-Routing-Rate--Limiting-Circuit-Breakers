"""API views for Payments (V2.1 health, V2.3 GET/POST)."""

from rest_framework import mixins, viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Payment
from .serializers import PaymentSerializer


class PaymentViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Only the three methods C1 documents: list, create and retrieve."""

    queryset = Payment.objects.all().order_by("id")
    serializer_class = PaymentSerializer

    def perform_create(self, serializer):
        # Kong's JWT plugin authenticates the caller and forwards the
        # consumer username. Persist it as required by C1.
        consumer = getattr(self.request, "kong_consumer", "") or "unknown"
        serializer.save(consumer=consumer)


@api_view(["GET"])
def health(request):
    """DB-free liveness endpoint used by Kong active health checks."""
    return Response({"status": "healthy"})
