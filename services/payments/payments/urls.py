"""Application URLs for the Payments service.

Kong strips /api/payments, so internally:
  /          -> list / create
  /{id}      -> retrieve
  /health    -> liveness

C1 documents no PUT/PATCH/DELETE, so no update/destroy routes are registered.
"""

from django.urls import include, path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter(trailing_slash=False)
router.register("", views.PaymentViewSet, basename="payment")

urlpatterns = [
    path("health", views.health, name="payments-health"),
    path("", include(router.urls)),
]
