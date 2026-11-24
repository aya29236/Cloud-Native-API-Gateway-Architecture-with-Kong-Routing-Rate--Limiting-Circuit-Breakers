"""Layer 3 / Step 3: Locust load generator for the Kong failover chaos test.

Start in headless mode with:
    docker compose --profile load run --rm locust \
      -f /mnt/locust/locustfile.py --headless -u 2 -r 1 -t 45s --host http://kong:8000

The rate stays below the frozen premium 100/min limit, so 429/5xx responses
during the replica-offline window indicate a failover problem, not a limiter.
"""

from __future__ import annotations

import os
from collections import Counter

from locust import HttpUser, between, events, task

served_by: Counter[str] = Counter()


@events.test_stop.add_listener
def report_served_by(environment, **_kwargs) -> None:
    """Print the replica distribution at the end of a headless run."""
    print("Locust X-Served-By distribution:", dict(sorted(served_by.items())))


class GatewayUser(HttpUser):
    host = os.getenv("BASE_URL", "http://127.0.0.1:8000")
    wait_time = between(1.3, 1.7)

    @task
    def accounts_health(self) -> None:
        response = self.client.get(
            "/api/accounts/health",
            headers={"apikey": os.getenv("APIKEY", "premium-demo-key")},
            name="/api/accounts/health",
        )
        if response.status_code != 200:
            response.failure(f"unexpected status {response.status_code}")
        served = (
            response.headers.get("X-Served-By")
            or response.headers.get("x-served-by")
            or "none"
        )
        served_by[served.lower()] += 1
