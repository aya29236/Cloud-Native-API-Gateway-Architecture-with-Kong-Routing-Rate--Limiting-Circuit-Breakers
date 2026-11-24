"""
Project-level URL configuration.

The service is reached through Kong at /api/accounts with strip_path
enabled, so internally the health endpoint is /health, not
/api/accounts/health. Keeping the prefix only in Kong avoids duplicating
routing rules in every service.
"""

from django.urls import include, path

urlpatterns = [
    path("", include("accounts.urls")),
]
