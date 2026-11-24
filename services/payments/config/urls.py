"""Project-level URL configuration for Payments.

Kong strips /api/payments, so internally the endpoints are /, /{id} and
/health. No prefix is duplicated here.
"""

from django.urls import include, path

urlpatterns = [
    path("", include("payments.urls")),
]
