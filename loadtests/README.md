# T1a Locust failure scenario

This load test sends normal requests to `/mock/echo` and `/mock/health` and
interleaves requests to `/mock/fail`. The defaults target the existing Kong
route through `http://localhost:8000`; that route strips `/mock` before
forwarding to the mock upstream. Configure the destination and request paths
with `LOCUST_HOST`, `LOCUST_NORMAL_PATHS` (comma-separated), and
`LOCUST_FAILURE_PATH`.

An API key is optional. If the deployment needs one, set both
`LOCUST_API_KEY_HEADER` (header name) and `LOCUST_API_KEY` (secret value) in
the environment; do not put credentials in this repository. For example, the
header name must be confirmed with the team before using the test against an
authenticated gateway.

Thresholds are configurable via `LOCUST_MAX_P95_MS` and
`LOCUST_MAX_ERROR_RATE`. Defaults are **2000 ms** for p95 and **0.30 (30%)**
for the error ratio. The scenario weights five normal task executions for each
failure-path task, so the 30% default allows the expected synthetic `/fail`
responses while still failing on a larger error ratio. The quitting event
prints request count, p95, and error ratio, then sets Locust's process exit
code to zero when both thresholds pass, or non-zero if either threshold is
exceeded or no requests completed. This makes the configured thresholds—not
the expected `/fail` responses alone—determine the process result.

## Install and run

Install the unpinned test dependencies from the repository root:

```powershell
python -m pip install -r loadtests/requirements-loadtest.txt
```

The installed and tested Locust version for this implementation is **2.47.0**;
the requirements intentionally do not pin a version.

Run headlessly against Kong and write the HTML and CSV reports beneath
`loadtests/reports/` (ignored by the repository's existing `reports/` rule):

```powershell
locust -f loadtests/locustfile_failure.py --headless `
  --users 10 --spawn-rate 2 --run-time 30s `
  --html loadtests/reports/failure.html `
  --csv loadtests/reports/failure
```

Set `LOCUST_HOST` to `http://127.0.0.1:8080`,
`LOCUST_NORMAL_PATHS=/echo,/health`, and
`LOCUST_FAILURE_PATH=/fail` to run against a local instance of
`mock-upstream/app.py` when Kong cannot be started. Use `LOCUST_HOST` rather
than `--host` for this locustfile's configurable default.

## Version and verification note

`requirements-loadtest.txt` contains unpinned `locust` and `PyYAML`.
PyYAML is used by `tests/test_fragments.py` to load and structurally validate
the Kong YAML fragments. This scenario was designed for the project's
`kong:3.9.1` and `/mock` route, but no live Kong behavior should be claimed
unless the stack has been started and observed.
