import os
import random
from pathlib import Path

from locust import HttpUser, between, events, task


def _csv_paths(variable, default):
    return tuple(
        path.strip()
        for path in os.getenv(variable, default).split(",")
        if path.strip()
    )


NORMAL_PATHS = _csv_paths("LOCUST_NORMAL_PATHS", "/mock/echo,/mock/health")
FAILURE_PATH = os.getenv("LOCUST_FAILURE_PATH", "/mock/fail")
API_KEY_HEADER = os.getenv("LOCUST_API_KEY_HEADER", "")
API_KEY = os.getenv("LOCUST_API_KEY", "")
MAX_P95_MS = float(os.getenv("LOCUST_MAX_P95_MS", "2000"))
MAX_ERROR_RATE = float(os.getenv("LOCUST_MAX_ERROR_RATE", "0.30"))

if not NORMAL_PATHS:
    raise ValueError("LOCUST_NORMAL_PATHS must contain at least one path")
if bool(API_KEY_HEADER) != bool(API_KEY):
    raise ValueError(
        "Set both LOCUST_API_KEY_HEADER and LOCUST_API_KEY, or neither"
    )
if MAX_P95_MS < 0:
    raise ValueError("LOCUST_MAX_P95_MS must be non-negative")
if not 0 <= MAX_ERROR_RATE <= 1:
    raise ValueError("LOCUST_MAX_ERROR_RATE must be between 0 and 1")

REPORT_DIR = Path(__file__).resolve().parent / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)


def _headers():
    if API_KEY_HEADER:
        return {API_KEY_HEADER: API_KEY}
    return {}


class FailureScenarioUser(HttpUser):
    host = os.getenv("LOCUST_HOST", "http://localhost:8000")
    wait_time = between(0.05, 0.2)

    @task(5)
    def normal_path(self):
        self.client.get(
            random.choice(NORMAL_PATHS),
            headers=_headers(),
            name="normal",
        )

    @task(1)
    def failure_path(self):
        self.client.get(
            FAILURE_PATH,
            headers=_headers(),
            name="failure",
        )


@events.quitting.add_listener
def enforce_thresholds(environment, **_kwargs):
    total = environment.stats.total
    requests = total.num_requests
    p95_ms = total.get_response_time_percentile(0.95) if requests else 0
    error_rate = total.fail_ratio if requests else 1.0
    print(
        "T1a thresholds: "
        f"requests={requests}, p95={p95_ms:.1f}ms (max {MAX_P95_MS:.1f}ms), "
        f"errors={total.num_failures}/{requests} ({error_rate:.1%}; "
        f"max {MAX_ERROR_RATE:.1%})"
    )
    breached = (
        requests == 0
        or p95_ms > MAX_P95_MS
        or error_rate > MAX_ERROR_RATE
    )
    environment.process_exit_code = 1 if breached else 0
    if breached:
        print("T1a threshold breach: exiting with status 1")
    else:
        print("T1a thresholds passed")
