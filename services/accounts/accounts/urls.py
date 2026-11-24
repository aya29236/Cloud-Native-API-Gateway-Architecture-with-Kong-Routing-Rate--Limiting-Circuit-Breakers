"""Application URLs for the Accounts service.

Kong strips the /api/accounts prefix, so internally:
  /            -> account list / create
  /{id}        -> account detail
  /health      -> liveness
  /fail,/slow,/flaky -> fault injection

`SimpleRouter(trailing_slash=False)` is used because C1 declares
`/api/accounts/{account_id}` without a trailing slash. The explicit health
and fault paths are registered before the router so they are never captured
by the detail route.
"""

from django.urls import include, path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter(trailing_slash=False)
router.register("", views.AccountViewSet, basename="account")

urlpatterns = [
    path("health", views.health, name="accounts-health"),
    path("fail", views.fail, name="accounts-fail"),
    path("slow", views.slow, name="accounts-slow"),
    path("flaky", views.flaky, name="accounts-flaky"),
    path("", include(router.urls)),
]
