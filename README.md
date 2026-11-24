# FinTech API Gateway — Topic 17

Gate 0 starter repository for Kong Open Source 3.9.1 (DB-less).

## Prerequisites (Windows)
- Docker Desktop with Linux containers enabled
- Git for Windows
- VS Code

Open this folder in VS Code. Run commands in the VS Code PowerShell terminal.

## First run
```powershell
Copy-Item .env.example .env
docker compose --profile core config
docker compose --profile core up -d --build
docker compose ps
```

Smoke tests:
```powershell
Invoke-RestMethod http://localhost:8000/mock/health
Invoke-RestMethod http://localhost:8000/mock/echo -Method Post -ContentType "application/json" -Body '{"hello":"world"}'
```

Kong's Admin API is bound to 127.0.0.1:8001 only. Do not expose it publicly.

Stop:
```powershell
docker compose --profile core down
```

## Kong deployment modes — theory overview

This section is the written version of the professor's required comparison between Kong's two installation modes. It can be pasted directly into the presentation. The implemented prototype uses **DB-less mode only**; A/B/C approved a theory-only treatment of PostgreSQL mode, so no separate `docker-compose.dbmode.yml` lab is claimed.

| Aspect | DB-less declarative mode (implemented) | PostgreSQL mode (theory only) |
|---|---|---|
| Source of truth | `kong/kong.yml` | Kong's PostgreSQL database |
| Key environment | `KONG_DATABASE=off`, `KONG_DECLARATIVE_CONFIG=/etc/kong/kong.yml` | `KONG_DATABASE=postgres`, `KONG_PG_HOST`, `KONG_PG_DATABASE`, `KONG_PG_USER`, `KONG_PG_PASSWORD` |
| Admin API | Read-only; changes are made by editing YAML and reloading/recreating Kong | Read/write; `GET/POST/PATCH/DELETE /services`, `/routes`, `/consumers`, `/plugins` mutate the database |
| Bootstrap | `kong config parse kong.yml`, then start Kong with the file mounted | Start Postgres, run `kong migrations bootstrap`, start Kong, optionally `kong config db_import kong.yml` once |
| Reload behaviour | Declarative config is loaded at startup; no migration state to manage | Schema migrations must be versioned and applied before upgrade |
| Best fit | Reproducible labs, CI, GitOps, immutable prototypes | Long-lived platforms with dynamic Admin API changes and multiple operators |
| Failure domain | Losing the container loses no gateway state; YAML remains in Git | Database availability and backups become critical |
| In this project | `docker-compose.yml`, `kong/kong.yml`, evidence `01`, `02`, `03` | Explained here only; not implemented |

Typical DB-less commands used by this project:

```powershell
docker compose exec kong kong config parse /etc/kong/kong.yml
docker compose --profile core up -d --force-recreate kong
curl.exe http://127.0.0.1:8001/services
curl.exe -X DELETE http://127.0.0.1:8001/services/mock-upstream  # returns 405
```

Typical PostgreSQL-mode commands for the presentation, **not run in this prototype**:

```bash
# 1. Start a PostgreSQL container and a Kong container on separate ports.
# 2. Initialise Kong's schema:
kong migrations bootstrap

# 3. Optional one-time import of the same declarative entities:
kong config db_import /etc/kong/kong.yml

# 4. Start Kong with KONG_DATABASE=postgres and the KONG_PG_* variables.
# 5. Prove dynamic configuration through the Admin API:
curl -i -X POST http://127.0.0.1:8001/services \
  --data name=demo --data url=http://accounts-1:8000
```

The teaching point: DB-less Kong treats `kong.yml` as immutable desired state, while PostgreSQL-mode Kong treats the Admin API and the database as live mutable state. Both expose the same proxy/plugin model; they differ in how configuration is stored, changed and operated.

## Presentation

The theoretical + practical PowerPoint deck is `presentation/FinTech_API_Gateway.pptx` (24 slides, English). It covers the professor's mandatory definitions, Kong entities, plugin phases, rate-limiting algorithms, active/passive health checks, two custom diagrams, DB-less vs PostgreSQL theory, the comparison matrix, Steps 1–4, evidence gallery, Final Gate result and the approved Ollama roadmap.

- Source outline: `presentation/slides.md`
- Reproducible builder: `python scripts/build_presentation.py` (stdlib OOXML, no third-party library)
- The demo recording is owned by the students; no demo video is generated in this repository.

## Gate 0 status
- [x] Initial repository layout
- [x] Contracts C1–C4 approved and frozen by all three students (C1 v0.3.0, C2 v0.1.1, C3 v0.2.1, C4 v0.2.1)
- [x] Sample Kong access-log fixture
- [x] Fake Alertmanager payload fixture
- [x] Mock upstream with `/health`, `/echo`, `/fail`, `/slow`
- [x] Compose skeleton and core profile
- [x] Branch protection configured on GitHub (re-verification requires an authenticated token)
- [x] All three students approve contracts
- [ ] LLM tool-calling spike completed by all three
- [x] Open questions sent to professor

## Continuous integration

`.github/workflows/ci.yml` runs on every push, pull request and manual dispatch:

- **P3a** — frozen contract markers, JSON fixtures/schema, Kong 3.9.1 `kong config parse`,
  Compose profiles, evidence filenames and Python lint.
- **P3b** — Accounts, Payments and Advisor pytest suites on PostgreSQL 16, plugin
  simulator/merge tests and a parse of every `kong/fragments/*.yml` file.
- **P3c** — `amtool check-config`, `promtool check rules` once Layer 4 rules exist,
  n8n verifier gate and builds of all four service images.
- **CI green gate** — single required check that fails unless P3a, P3b and P3c all pass.

The fragment merger in `scripts/fragment_lab.py` is stdlib-only; no PyYAML is used.
The JWT helper `scripts/make_jwt.py` uses real PyJWT, pinned in `requirements-dev.txt`
and installed by P3b.

### CI red/green evidence (18)

Evidence `screenshots/18_ci_red_green.png` records the real Actions behaviour:

1. Run #9 (`817e044`) intentionally set `_format_version: "9.9"` in `kong/kong.yml`.
   P3a failed at `Parse live declarative Kong config with Kong 3.9.1`, and the aggregate
   `CI green gate` failed. P3b and P3c still passed, showing the guard is specific.
2. Run #10 (`1ad4904`) restored `_format_version: "3.0"`. All four jobs passed again.

No branch was merged into `main`; the verification stayed on `ci/prototype-pipeline`.

## Accounts service — Student B (V1)

Local development (PostgreSQL 16 runs in Docker, Django runs on the host):

```powershell
docker compose --profile core up -d postgres
cd services/accounts
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8010
```

Then `Invoke-RestMethod http://127.0.0.1:8010/health -Headers @{'Kong-Request-ID'='req-1'}` returns `{"status":"healthy"}` and echoes the correlation headers.

- [x] V1.1 Django project/app structure and pinned dependencies
- [x] V1.2 DB-free `/health`
- [x] V1.3 `X-Served-By`, `Kong-Request-ID`, `X-Consumer-Username` and structured logs
- [x] V1.4 `Account` model, PostgreSQL 16 and migration `0001_initial` (8 tests green)
- [x] V1.5 `ModelSerializer`, `ViewSet` + router, and `/fail`, `/slow`, `/flaky` (22 tests green)
- [x] V1.6 Dockerfile, `accounts-1`/`accounts-2`, full C1 contract tests (22/22 green inside the container)

To run both replicas (plus the one-shot migration job):

```powershell
docker compose --profile core up -d --build accounts-migrate accounts-1 accounts-2
docker compose --profile core exec -T accounts-1 python -m pytest
```

`X-Served-By` is the container hostname, so it is exactly `accounts-1` or `accounts-2`.

PostgreSQL is published on `127.0.0.1:5433` (DEC-007). The containers use Django's development server, not gunicorn (DEC-006).

## Payments service — Student B (V2)

- [x] V2.1 Django project/app structure, DB-free `/health`, gateway headers and logging (5 tests green)
- [x] V2.2 `Payment` model and migration (stores the Kong `X-Consumer-Username`; 8 tests green)
- [x] V2.3 serializer, GET/POST API and C1 contract tests (22 tests green; consumer captured from Kong header)
- [x] V2.4 Dockerfile, `payments-1`/`payments-2`, full C1 contract tests (22/22 green inside the container)

Accounts and Payments share one PostgreSQL 16 database (DEC-008); table names are app-prefixed. `payments-migrate` waits for `accounts-migrate` so a clean-clone start cannot race on the shared `django_migrations` table.

## AI Advisor service — Student B shell, Student C logic (V3)

- [x] V3.1 FastAPI shell, `/health`, Pydantic C1 models, stub `/analyze` ("No verified data"), `/stats`, `X-Served-By` (8 tests green)
- [x] V3.2 `advisor-1`/`advisor-2` containers with read-only `kong-logs` mount (8/8 green inside the container)
- [x] V3.3 Layer 5 verified tool-calling analyzer: `read_logs` → `filter_records` → `aggregate` → `verify_answer`, with grounded client-IP/route stats and exact C1 fallback when no tool result supports the question

FastAPI serves Swagger UI at `http://127.0.0.1:8000/docs` once Kong routes `/api/advisor` at Layer 1. Locally: `cd advisor; .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload`.

### Layer 5 / M5 — verified analyzer

`advisor/app/analyzer.py` never invents an answer or calls an external LLM. It reads only the read-only `/var/log/kong/access.json` mount (`ADVISOR_LOG_PATH`), accepts only C2 0.1.1-valid records, and returns citations `[L<id>]` whose ids are checked against the records loaded for that request. Every number in the summary comes from the `aggregate` tool result, including `client_ip_counts`, `distinct_client_ips` and `top_client_ip` for offending-IP/route questions. If there are no valid records, no matching records, a forged citation, or any other failed check, the response is exactly `summary: "No verified data"`, `verified: false`, `citations: []`.

```powershell
cd advisor
.\.venv\Scripts\python.exe -m pytest

# Live through Kong after rebuilding the advisor replicas:
docker compose --profile core up -d --build advisor-1 advisor-2
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/advisor/analyze `
  -Headers @{ apikey = 'premium-demo-key' } -ContentType 'application/json' `
  -Body '{"question":"How many requests were logged?"}'
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/advisor/analyze `
  -Headers @{ apikey = 'premium-demo-key' } -ContentType 'application/json' `
  -Body '{"question":"Which client IPs caused errors?"}'
Invoke-RestMethod http://127.0.0.1:8000/api/advisor/stats -Headers @{ apikey = 'premium-demo-key' }

# Formal evidence 22 (real PowerShell terminal window):
.\scripts\capture-terminal-evidence.ps1 -Id '22' -Output 'screenshots\22_layer5_verified_analyzer.png'
```

The response carries the five frozen C1 fields plus a `tool_trace` that names each tool, its arguments and its result. No raw Kong headers or credentials are copied into the trace.

## Monitoring and automation — Student B (M2/M3)

- [x] M2 `monitoring/alertmanager.yml`: n8n webhook receiver, `group_by: [alertname, service]`, `group_wait: 5s`, `group_interval: 30s`, `repeat_interval: 4h`, inhibition of `KongCircuitOpen` by `KongUpstreamTargetUnhealthy`. `amtool check-config` passes; fake alerts were accepted, grouped and suppressed as designed. Delivered to n8n once M3 deploys it.
- [x] M3 n8n router + circuit-open and 429 workflows (JSON exported to `n8n/workflows/`; both C3 fake payloads reached the channel; 4/4 executions green)

Start Alertmanager with `docker compose --profile monitoring up -d alertmanager` (UI at `http://127.0.0.1:9093`).

### M3 n8n runbook

```bash
docker compose --profile monitoring up -d n8n notify-sink
# First install / after a change to n8n/workflows/*.json:
docker compose --profile monitoring exec -T n8n n8n import:workflow --separate --input=/workflows
docker compose --profile monitoring exec -T n8n n8n update:workflow --all --active=true
docker compose --profile monitoring restart n8n

python n8n/workflows/validate.py          # offline structure check

curl -X POST http://127.0.0.1:5678/webhook/alertmanager \
  -H "Content-Type: application/json" \
  --data-binary @n8n/fixtures/fake-circuit-open.json
curl -X POST http://127.0.0.1:5678/webhook/alertmanager \
  -H "Content-Type: application/json" \
  --data-binary @n8n/fixtures/fake-429-spike.json

docker compose --profile monitoring logs notify-sink   # channel messages
```

Flow: `Webhook /alertmanager` → normalize → Switch on `alertname` → `Webhook /circuit-open` or `/429` → build a question about offending IPs/routes in the alert window → `POST $ADVISOR_URL` with the `apikey` header → format → `POST $TELEGRAM_API_BASE/bot…/sendMessage`.

`ADVISOR_URL` is `http://kong:8000/api/advisor/analyze` (available at Layer 1). Until then the Advisor step uses `onError: continueRegularOutput` and the message shows the safe `"No verified data"` fallback. `TELEGRAM_API_BASE` defaults to the local `notify-sink` demo channel; set it to `https://api.telegram.org` for real delivery. `notify-sink` logs are the evidence-14 artifact at Layer 4.

## Layer 1 — Kong topology (G1, Student B)

- [x] G1 `kong/kong.yml`: `_format_version "3.0"`, three services/routes (GET+POST, `strip_path: true`), three upstreams × two targets, round-robin, retries=2, connect/read/write timeouts; Gate 0 mock route retained.
- [x] G1 Admin API read curls (`/services`, `/routes`, `/upstreams`, `/upstreams/<name>/health`, `/status`) and DB-less read-only explanation.
- [x] Evidence **01**, **02** and **03** captured (Student B).

Public routes → internal upstreams:

| Public route | Service | Upstream | Targets |
|---|---|---|---|
| `/api/accounts` | `accounts` | `accounts-upstream` | `accounts-1:8000`, `accounts-2:8000` |
| `/api/payments` | `payments` | `payments-upstream` | `payments-1:8000`, `payments-2:8000` |
| `/api/advisor` | `advisor` | `advisor-upstream` | `advisor-1:8000`, `advisor-2:8000` |

`strip_path: true` means `/api/accounts/health` reaches the service as `/health`. Kong is **DB-less** (`KONG_DATABASE=off`): `kong/kong.yml` is the only source of truth and the Admin API on `:8001` is read-only (GET succeeds, POST/PUT/DELETE return 400/405). `:8100/status` is published on `127.0.0.1` for the health/status curl.

G1 runbook (verifies the evidence):
```powershell
docker compose --profile core up -d --build
docker run --rm -e KONG_DATABASE=off -v "${PWD}\kong:/etc/kong:ro" kong:3.9.1 kong config parse /etc/kong/kong.yml
# expect: parse successful

curl.exe -s http://127.0.0.1:8001/services
curl.exe -s http://127.0.0.1:8001/routes
curl.exe -s http://127.0.0.1:8001/upstreams
curl.exe -s http://127.0.0.1:8001/upstreams/accounts-upstream/health
curl.exe -s http://127.0.0.1:8100/status
curl.exe -s -o NUL -w '%{http_code}' -X DELETE http://127.0.0.1:8001/services/mock-upstream
# expect 405 (read-only)

1..6 | ForEach-Object { (Invoke-WebRequest http://127.0.0.1:8000/api/accounts/health).Headers['X-Served-By'] }
1..6 | ForEach-Object { (Invoke-WebRequest http://127.0.0.1:8000/api/payments/health).Headers['X-Served-By'] }
1..6 | ForEach-Object { (Invoke-WebRequest http://127.0.0.1:8000/api/advisor/health).Headers['X-Served-By'] }
# expect the two replica hostnames alternating
```

## Layer 3 / Step 3 — health checks and chaos failover

- [x] `kong/fragments/60-healthchecks.yml`: active `/health` polling and passive 5xx/tcp/timeout checks on all three upstreams; HTTP 429 is excluded so rate limiting does not mark a target down. Explicitly merged into `kong/kong.yml` and parsed in all eight `verify_fragments.py` scenarios.
- [x] Real load generators: `tests/load/k6_failover.js` and `tests/load/locustfile.py` under the `load` Compose profile (`grafana/k6:1.8.0`, `locustio/locust:2.47.0`).
- [x] Live chaos result: with a 2-VU 45-second k6 run, stopping `accounts-2` made `accounts-upstream` report `accounts-2=UNHEALTHY` while `accounts-1=HEALTHY`; restarting it recovered both to `HEALTHY`. k6 recorded `100.00%` successful checks and `0.00%` failed requests. A 10-second Locust run independently recorded `0(0.00%)` failures with both replicas in `X-Served-By`.

```powershell
# Load the healthchecks into live Kong and verify all explicit merges:
docker compose --profile core up -d --force-recreate kong
python scripts/verify_fragments.py
curl.exe -s http://127.0.0.1:8001/upstreams/accounts-upstream/health

# Concurrent load while one replica is offline:
docker compose --profile load run --rm k6
docker compose --profile core stop accounts-2
docker compose --profile core start accounts-2
docker compose --profile load run --rm locust `
  -f /mnt/locust/locustfile.py --headless --host http://kong:8000 `
  -u 2 -r 1 -t 10s --only-summary

# Formal evidence 24 (real PowerShell terminal window):
.\scripts\capture-terminal-evidence.ps1 -Id '24' -Output 'screenshots\24_layer3_chaos_failover.png'
```

Evidence (real screenshots of the PowerShell terminal window, captured by `scripts/capture-terminal-evidence.ps1` while the commands run):

| ID | File | Format | Storage | Verification |
|---|---|---|---|---|
| 01 | `screenshots/01_compose_ps_kong_version.png` | PNG | repo `screenshots/` | `docker compose ps` (all healthy) + `kong version` → 3.9.1 |
| 02 | `screenshots/02_kong_config_parse.png` | PNG | repo `screenshots/` | `kong config parse` → `parse successful`, plus `kong.yml` head |
| 03 | `screenshots/03_admin_api_read.png` | PNG | repo `screenshots/` | five Admin API read curls + DELETE → 405 |
| 08 | `screenshots/08_layer2_gateway_headers.png` | PNG | repo `screenshots/` | C1 correlation/consumer/served-by headers, replica alternation, CORS preflight and 413 |
| 19 | `screenshots/19_layer2_auth_matrix.png` | PNG | repo `screenshots/` | live key-auth/JWT matrix + merged plugin inventory on Accounts/Payments/Advisor |
| 20 | `screenshots/20_layer2_rate_token_tls.png` | PNG | repo `screenshots/` | live G3 tiered limits, G4 token-bucket parity and G5 HTTPS/SAN checks |
| 21 | `screenshots/21_layer2_telemetry.png` | PNG | repo `screenshots/` | `kong_*` metrics on :8100 plus a C2 0.1.1 `file-log` field check |
| 22 | `screenshots/22_layer5_verified_analyzer.png` | PNG | repo `screenshots/` | 15 Advisor tests green, verified overview, 429 answer with citations, grounded client-IP stats, exact 503 fallback, and `/stats` through Kong |
| 23 | `screenshots/23_layer4_prometheus_m1.png` | PNG | repo `screenshots/` | M1 contract check PASS, promtool config/rules SUCCESS, Kong target up, 3 rules loaded, Alertmanager connected |
| 24 | `screenshots/24_layer3_chaos_failover.png` | PNG | repo `screenshots/` | active/passive healthchecks, k6 load with `accounts-2` offline, UNHEALTHY → HEALTHY recovery, 0% failures, Locust cross-check |
| 25 | `screenshots/25_final_gate_audit.png` | PNG | repo `screenshots/` | `scripts/final_gate_audit.py` PASS on all 53 automated checks, with explicit WARN items |

Images are stored in `screenshots/NN_topic.png` per Master Plan §8.3. Each PNG is a direct screenshot of a visible PowerShell window running the live commands; regenerate one with:

```powershell
.\scripts\capture-terminal-evidence.ps1 -Id '08' -Output 'screenshots\08_layer2_gateway_headers.png'
```

`scripts/capture-evidence.ps1` remains available for plain transcript rendering but is not the source of these PNGs.

## Independent wave — G2–G7 (Students A and C)

No numbered evidence was due for the independent wave; each module's own test was green and the transcript is saved in `tests/fragments/independent-wave-results.txt`. Layer 2 / I3 explicitly merged all six G2–G7 fragments into the live `kong/kong.yml`; Layer 3 added the seventh `60-healthchecks.yml` fragment. The fragment files remain the source definitions and the live file is the DB-less source of truth.

| WP | Owner | Fragment / script | Mock-upstream result |
|---|---|---|---|
| G2 | A | `kong/fragments/10-auth.yml`, `scripts/make_jwt.py`, `scripts/gen_keys.sh` | key-auth 401/200/401; JWT 200, bad-JWT 401, wrong-iss 401 |
| G3 | C | `kong/fragments/20-ratelimit.yml` | free 10/min → 10×200 then 429; premium 100/min → 12×200; `X-RateLimit-*` + `Retry-After` |
| G4 | A | `kong/fragments/25-tokenbucket.yml`, `kong/plugins/token-bucket/{schema,handler}.lua`, `scripts/token_bucket_sim.py` | simulator `111110000000` == live Kong; 1.2 s refill 200; premium 12×200 |
| G5 | A | `kong/fragments/50-tls.yml`, `scripts/gen_cert.sh` | HTTPS :8443 200 with CA; SAN `DNS:localhost, IP:127.0.0.1`; upstream stays HTTP |
| G6 | C | `kong/fragments/30-transform.yml` | `Kong-Request-ID` echoed; `X-Gateway` added / `X-Debug` removed; CORS preflight 200 + exposed headers; 413 over 1 KB |
| G7 | A | `kong/fragments/40-telemetry.yml` | `kong_*` metrics on `:8100/metrics`; file-log line has all C2 0.1.1 fields |

## Layer 2 / I3 — live integration

The live `kong/kong.yml` now contains the Layer 1 services/upstreams plus one explicit copy of every approved G2–G7 section. No runtime merge is performed. `docker-compose.yml` loads the custom Lua plugin, declares its shared dictionary, enables the `:8443 ssl` listener and runs a one-shot `kong-logs-init` container so the named log volume is writable by Kong's uid.

Live checks against the real Django Accounts, Django Payments and FastAPI Advisor services:

```powershell
# Auth matrix and merged plugin inventory
curl.exe -s -o NUL -w "%{http_code}" http://127.0.0.1:8000/api/accounts/health
curl.exe -s -o NUL -w "%{http_code}" -H "apikey: free-demo-key" http://127.0.0.1:8000/api/accounts/health
$t = python scripts/make_jwt.py --iss fintech-free
curl.exe -s -o NUL -w "%{http_code}" -H "Authorization: Bearer $t" http://127.0.0.1:8000/api/payments/health

# C1 headers, CORS preflight and 413 on every real POST service
curl.exe -s -D - -o NUL -H "apikey: premium-demo-key" http://127.0.0.1:8000/api/accounts/health
curl.exe -s -D - -o NUL -X OPTIONS -H "Origin: http://localhost:3000" `
  -H "Access-Control-Request-Method: POST" http://127.0.0.1:8000/api/accounts

# G4 uses --count 5 live: it exercises only the guaranteed initial capacity.
# Consumer-scoped G3 rate limiting is global in I3, so the live burst is
# restarted/isolated from the 10/min tier check below.
docker compose restart kong
python tests/fragments/verify_token_bucket.py --url http://127.0.0.1:8000 --count 5

# G5 and G7
curl.exe --cacert certs\localhost.crt https://localhost:8443/api/accounts/health `
  -H "apikey: premium-demo-key"
curl.exe -s http://127.0.0.1:8100/metrics | Select-String '^kong_'
docker compose exec -T kong sh -lc 'tail -n 1 /var/log/kong/access.json'
```

The `correlation-id` and `request-size-limiting` plugin instances are global in the live file so every C1 operation has a `Kong-Request-ID` and every POST has the 1024-byte 413 guard; this is an I3 integration choice and does not change the frozen contracts.

### Fragment lab runbook

`scripts/fragment_lab.py` no longer merges YAML: it only parses or boots whatever `kong/kong.yml` explicitly contains. With no fragment arguments, `scripts/verify_fragments.py` writes each selected section explicitly into `kong/kong.yml`, runs real Kong 3.9.1, and restores the previous file in a `finally` block. There is no PyYAML and no generated temporary merged config. For an interactive lab, use `verify_fragments.py <fragments...>` to write that explicit config, boot it with `fragment_lab.py up`, then run `verify_fragments.py --restore` before moving on.

Prerequisites for the Windows host — use the supplied Git for Windows and standalone OpenSSL-Win64:

```powershell
# PowerShell
python -m pip install -r requirements-dev.txt   # PyJWT 2.15.1 for scripts/make_jwt.py
$env:OPENSSL_BIN = "C:\Program Files\OpenSSL-Win64\bin\openssl.exe"
$env:PATH = "C:\Program Files\Git\usr\bin;$env:PATH"
```

```cmd
REM Command Prompt (cmd.exe) - note: NO leading & here
python -m pip install -r requirements-dev.txt
set "OPENSSL_BIN=C:\Program Files\OpenSSL-Win64\bin\openssl.exe"
set "PATH=C:\Program Files\Git\usr\bin;%PATH%"
```

`& "C:\path\to\exe"` is PowerShell-only. In `cmd.exe`, write `"C:\path\to\exe" --arg` with no `&`.

```powershell
# Parse every fragment through an explicit merge into kong/kong.yml, then restore it.
python scripts/verify_fragments.py

# Rate limiting (G3): write the explicit merge, boot it, then restore.
python scripts/verify_fragments.py kong/fragments/10-auth.yml kong/fragments/20-ratelimit.yml
python scripts/fragment_lab.py up --name lab-rate --proxy 18200 --admin 18201
python scripts/fragment_lab.py down lab-rate
python scripts\verify_fragments.py --restore

# custom Lua plugin (G4)
python scripts\verify_fragments.py kong\fragments\10-auth.yml kong\fragments\25-tokenbucket.yml
python scripts\fragment_lab.py up `
  --name lab-token --proxy 18400 --admin 18401 --plugins bundled,token-bucket `
  --plugin-mount kong\plugins\token-bucket
python tests/fragments/verify_token_bucket.py --url http://127.0.0.1:18400
python scripts\fragment_lab.py down lab-token
git checkout -- kong\kong.yml

# TLS (G5) - regenerate demo credentials/certificate with Git bash + OpenSSL-Win64 4.1.0
& "C:\Program Files\Git\bin\bash.exe" scripts\gen_keys.sh
& "C:\Program Files\Git\bin\bash.exe" scripts\gen_cert.sh
python scripts\verify_fragments.py kong\fragments\50-tls.yml
python scripts\fragment_lab.py up --name lab-tls --proxy 18500 --tls 18943
curl.exe --cacert certs\localhost.crt https://localhost:18943/api/accounts/health
& "C:\Program Files\OpenSSL-Win64\bin\openssl.exe" s_client -connect localhost:18943 -servername localhost -CAfile certs\localhost.crt -brief
python scripts\fragment_lab.py down lab-tls
git checkout -- kong\kong.yml

# telemetry (G7)
$logs = "$env:TEMP\opencode\kong-logs-lab"
python scripts\verify_fragments.py kong\fragments\40-telemetry.yml
python scripts\fragment_lab.py up --name lab-telemetry --proxy 18600 --log-mount $logs
python scripts\fragment_lab.py down lab-telemetry
git checkout -- kong\kong.yml
```

Same G5 commands in `cmd.exe` (no `&`):

```cmd
set "OPENSSL_BIN=C:\Program Files\OpenSSL-Win64\bin\openssl.exe"
"C:\Program Files\Git\bin\bash.exe" scripts\gen_keys.sh
"C:\Program Files\Git\bin\bash.exe" scripts\gen_cert.sh
"C:\Program Files\OpenSSL-Win64\bin\openssl.exe" s_client -connect localhost:18943 -servername localhost -CAfile certs\localhost.crt -brief
```

Notes:
- Kong's `rate-limiting` plugin counts **fixed-window requests per consumer** (`limit_by: consumer`, `policy: local` = per-node in-memory counter) and emits `X-RateLimit-*` plus `Retry-After`; verified against the Kong 3.9 plugin page.
- `token-bucket` is `PRIORITY 750` (below `key-auth` 1250 and `jwt` 1000), uses `KONG_NGINX_HTTP_LUA_SHARED_DICT="token_bucket 1m"`, and calls `ngx.update_time()` so worker time caches cannot distort refill.
- `scripts/make_jwt.py` uses PyJWT and suppresses only PyJWT's `InsecureKeyLengthWarning` because the committed secrets are short demo fixtures, not production keys.
- `scripts/gen_keys.sh` and `scripts/gen_cert.sh` prefer `C:\Program Files\OpenSSL-Win64\bin\openssl.exe`, honour `OPENSSL_BIN`, then fall back to PATH; they fail loudly if none is usable. Generated `scripts/demo_secrets/` and raw PEM files are local-only; the embedded demo certificate in `50-tls.yml` is regenerated by `scripts/gen_cert.sh`.
- `request-size-limiting` uses `allowed_payload_size: 1024` with `size_unit: bytes`; Kong's default unit is megabytes, so a bare `1` would allow 1 MB, not 1 KB.
- G7 compared the real `file-log` line with C2 `0.1.1`: all required fields matched, so no contract version bump was needed.

## Layer 4 / M1 — Prometheus and alert rules (Student C)

- [x] C3 editorial PATCH `0.2.0` → `0.2.1` after live M1: `kong_upstream_target_health` is a state indicator with value `1` when the labelled state is populated, and all three rules now carry the `service` label needed by Alertmanager grouping/inhibition.
- [x] `monitoring/prometheus.yml` scrapes `kong:8100/metrics` every 5s and forwards alerts to `alertmanager:9093`.
- [x] `monitoring/rules/alerts.yml` implements the three frozen C3 v0.2.1 alert expressions.
- [x] CI runs `promtool check config` and `promtool check rules` with Prometheus `v3.16.0`.

Start the monitoring stack and run the live contract check:

```powershell
docker compose --profile core --profile monitoring up -d prometheus alertmanager
python scripts/verify_metrics_contract.py

# Formal evidence 23 (real PowerShell terminal window):
.\scripts\capture-terminal-evidence.ps1 -Id '23' -Output 'screenshots\23_layer4_prometheus_m1.png'
```

Prometheus UI: `http://127.0.0.1:9090`. Alertmanager UI: `http://127.0.0.1:9093`.

## Final Gate audit

`scripts/final_gate_audit.py` is a stdlib-only audit of the live prototype and the repository artifacts. It checks the four frozen contracts, Kong topology/healthchecks, C1 auth and headers, the live C2 access-log line, C3 metrics/alerts/n8n, C4 Compose/load generators, the Layer 5 analyzer, evidence files, CI job structure and branch invariants. The current run is **PASS WITH WARNINGS**: 54/54 automated checks pass, while the script deliberately reports these open items instead of hiding them:

- Owner evidence IDs `10`, `11`, `13` and `14` are not present in `screenshots/`; `14` remains blocked on Telegram test credentials.
- Gate 0 still has one unchecked question: the LLM tool-calling spike completed by all three students. The professor-questions item is now confirmed sent by A/B/C.
- No authenticated GitHub token was available to re-read `main` branch protection; the earlier applied protection is unchanged but not re-verified in this run.

```powershell
python scripts/final_gate_audit.py

# Formal evidence 25 (real PowerShell terminal window):
.\scripts\capture-terminal-evidence.ps1 -Id '25' -Output 'screenshots\25_final_gate_audit.png'
```

## Contract change rule
Contracts are versioned independently. Any breaking change requires a MAJOR version bump and approval from A, B and C. Backward-compatible additions require a MINOR bump. Editorial corrections require a PATCH bump. Record every accepted change in `decisions.md`.

## Important
C1–C4 are approved and frozen by all three students and are the specifications the services implement. G7 verified the real Kong access-log fields against C2, and M1 verified the real `/metrics` names and labels against C3; the M1 finding was handled by the approved C3 v0.2.1 PATCH. Any future mismatch requires an approved, versioned contract change.
