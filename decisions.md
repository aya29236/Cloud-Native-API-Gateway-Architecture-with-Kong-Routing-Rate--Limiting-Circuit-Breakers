# Architecture decisions

## DEC-001 — Contract-first integration
- Status: Approved by Student A, Student B and Student C at Gate 0
- Decision: C1–C4 are versioned contracts. Services, Kong configuration, monitoring and the analyzer implement these contracts rather than inventing independent formats.

## DEC-002 — Kong deployment mode
- Status: Accepted from master plan
- Decision: Use Kong Open Source 3.9.1 in DB-less mode with declarative `kong.yml`.

## DEC-003 — Gate 0 mock upstream
- Status: Proposed
- Decision: Provide deterministic `/health`, `/echo`, `/fail`, and `/slow` endpoints for integration work before real services exist.

## DEC-004 — Student C participation and C1 status correction
- Status: Applied (editorial correction)
- Decision: Student C (Wafe Bziouiche) is no longer absent and participates in contract review. All "Student C is absent" statements are removed from the contract pack. C1 received a PATCH bump from 0.2.0 to 0.2.1; no interface, schema or behavior changes. Approval followed separately in DEC-005.
- Approval required: Student A, Student B, Student C.

## DEC-005 — Gate 0 contract finalization and approval
- Status: Approved by Student A (Eya Derouiche), Student B (Aya Fayachi) and Student C (Wafe Bziouiche)
- Decision: All four contracts are approved and frozen at Gate 0. C1 is bumped 0.2.1 to 0.3.0 (MINOR) to match the exact Master Plan requirements: per-service methods, paths, status codes, key-auth/JWT, the X-Served-By, Kong-Request-ID and X-Consumer-Username headers, internal port 8000, /health responses, and the advisor POST /analyze {question} -> {summary, stats, citations, tool_trace, verified} contract. C2 is bumped 0.1.0 to 0.1.1 (PATCH, metadata only). C3 is bumped 0.1.0 to 0.2.0 (MINOR) with canonical metric names and labels, concrete 503/429/health thresholds, severities, annotations and a complete Alertmanager webhook sample. C4 is bumped 0.1.0 to 0.2.0 (MINOR) adding PostgreSQL 16, the Gate 0 mock upstream, Locust/k6, monitoring/automation/AI containers and the DB-mode lab. The heading version in `contracts/README.md` is that README's own version and is unchanged.
- Verification qualifications: G7 verifies real Kong 3.9.1 access-log fields against C2 and M1 verifies real /metrics names against C3; any mismatch requires an approved, versioned change with contract tests rerun.

## DEC-006 — Django development server replaces gunicorn
- Status: Approved by Student A (Eya Derouiche), Student B (Aya Fayachi) and Student C (Wafe Bziouiche)
- Decision: The Master Plan lists gunicorn for the accounts-1/2 and payments-1/2 containers. The project owner directed that gunicorn not be used and that Django's development server be kept instead. Gunicorn 27 also cannot start on Windows (`fcntl` is Unix-only). Therefore `requirements.txt` and the future Dockerfiles use `python manage.py runserver 0.0.0.0:8000`. The WSGI application object and every C1 behavior are unchanged; only the process manager differs.

## DEC-007 — PostgreSQL host port 5433
- Status: Applied (environment constraint)
- Decision: Windows reserves/excludes host port 5432, so PostgreSQL 16 is published as `127.0.0.1:5433:5432`. Services on the Compose `gateway` network still connect to `postgres:5432` internally. `.env`, `.env.example` and `services/accounts/config/settings.py` default `POSTGRES_PORT` to 5433.

## DEC-008 — Shared PostgreSQL database for Accounts and Payments
- Status: Approved by Student A (Eya Derouiche), Student B (Aya Fayachi) and Student C (Wafe Bziouiche)
- Decision: Both Django services connect to the same PostgreSQL 16 container and the same database (`accounts`). Django app labels prefix the table names (`accounts_account`, `payments_payment`) and both apps' migrations are recorded in the shared `django_migrations` table. This keeps a single PostgreSQL target for the C4 DB-mode lab and avoids recreating an already-initialized volume. No contract in C1–C4 depends on separate database names.

## DEC-009 — Real CI pipeline before Layer 2
- Status: Applied on the requested `ci/prototype-pipeline` branch
- Decision: Replace the Gate 0 CI skeleton with three real jobs (P3a repository checks, P3b pytest/Kong/plugin mocks, P3c amtool/promtool/verifier/image builds) plus one aggregate green gate. `scripts/fragment_lab.py` no longer merges fragments at all; CI instead uses `scripts/verify_fragments.py` to write explicit, dependency-aware merges into `kong/kong.yml` with no YAML parser library, as the project owner required. The pipeline runs on every push, pull request and manual dispatch. Evidence 18 was captured from real Actions runs #9 (red: broken `kong.yml`) and #10 (green: restored `kong.yml`); branch protection is still to be configured on GitHub.

## DEC-010 — Verified lab toolchain and G6 byte limit
- Status: Applied after the A/B/C approval following evidence 18
- Decision: `scripts/make_jwt.py` uses real PyJWT 2.15.1 pinned in `requirements-dev.txt` instead of hand-rolled HS256. `scripts/gen_keys.sh` and `scripts/gen_cert.sh` use Git for Windows bash and prefer the supplied OpenSSL-Win64 4.1.0 (`C:\Program Files\OpenSSL-Win64\bin\openssl.exe`, overridable with `OPENSSL_BIN`), fail loudly when no real OpenSSL is usable, and handle MSYS path conversion. `kong/fragments/30-transform.yml` sets `allowed_payload_size: 1024` with `size_unit: bytes` so the documented 1 KB `request-size-limiting` behavior is real. The G2–G7 live redo passed 25/25 checks against the Gate 0 mock upstream using these exact tools; the transcript is in `tests/fragments/independent-wave-results.txt`.

## DEC-011 — Explicit fragment merges into kong.yml
- Status: Applied after the owner's explicit correction
- Decision: `scripts/fragment_lab.py` accepts no fragment paths and contains no merge logic; it only parses or boots the current `kong/kong.yml`. `scripts/verify_fragments.py` uses stdlib text handling (no PyYAML, no temporary merged config) to write each dependency-aware scenario explicitly into `kong/kong.yml`, parse it with Kong 3.9.1, and restore the previous file. CI runs 7 scenarios; standalone parses of consumer-scoped fragments are intentionally excluded because they require `10-auth.yml`. The live G2–G7 redo used the same explicit-merge helper before every container boot and restored `kong.yml` at the end.

## DEC-012 — Layer 2 / I3 live fragment integration
- Status: Applied after explicit A/B/C approval for the next implementation step
- Decision: All six approved G2–G7 fragments are explicitly merged into the live `kong/kong.yml`, which remains the DB-less source of truth. `docker-compose.yml` loads `bundled,token-bucket`, declares the `token_bucket 1m` shared dictionary, mounts the custom Lua plugin, enables `0.0.0.0:8443 ssl`, and sets the n8n `ADVISOR_APIKEY` default to `premium-demo-key` so workflow calls are authenticated without consuming the free 10/min allowance. A one-shot `kong-logs-init` container chowns the named `kong-logs` volume before Kong starts so the contracted `/var/log/kong/access.json` file-log path is writable. In the live file, `correlation-id` and `request-size-limiting` are global so every C1 operation has `Kong-Request-ID` and every POST has the 1 KB 413 guard; this is an integration scope choice, not a contract change. The consumer-scoped G3 limiter is global across services, so the live G4 burst uses `--count 5` (the guaranteed initial capacity) and the G3 tier check is run after a fresh Kong restart. `scripts/verify_fragments.py --restore` replaces the earlier unsafe `git checkout` runbook now that the merged config is committed work.

## DEC-013 — Terminal-window evidence screenshots
- Status: Applied after the owner's correction
- Decision: Formal evidence PNGs `01`, `02`, `03`, `08`, `19`, `20` and `21` are direct screenshots of a visible PowerShell terminal window captured by `scripts/capture-terminal-evidence.ps1` and `scripts/terminal-evidence-run.ps1`. This replaces the earlier plan to use browser-page screenshots; the transcript renderer `scripts/capture-evidence.ps1` remains available but is not the source of these PNGs.

## DEC-014 — C3 PATCH 0.2.1 after live M1
- Status: Applied after explicit A/B/C approval
- Decision: Live M1 confirmed the canonical metric names on Kong 3.9.1 but found that `kong_upstream_target_health` is a state indicator with value `1` when the labelled state is populated; the original `== 0` expression would have fired on healthy targets. C3 is bumped from `0.2.0` to `0.2.1` as an editorial PATCH: the unhealthy rule selects `state=~"unhealthy|dns_error" == 1`, and all three rules derive the `service` label from the route/upstream name so Alertmanager grouping and inhibition work as designed. Alert names, thresholds, severities and webhook fields are unchanged.

## DEC-015 — Layer 4 / M1 Prometheus implementation
- Status: Applied after explicit A/B/C approval for the next implementation step
- Decision: `monitoring/prometheus.yml` scrapes `kong:8100/metrics` every 5s and alerts `alertmanager:9093`; `monitoring/rules/alerts.yml` implements the three frozen C3 v0.2.1 expressions; `scripts/verify_metrics_contract.py` performs the live M1 check. Prometheus is pinned to `v3.16.0` in Compose and CI, which now runs both `promtool check config` and `promtool check rules`.

## DEC-016 — Layer 5 / M5 verified analyzer
- Status: Applied after explicit A/B/C approval for the next implementation step
- Decision: The V3.1 stub is replaced by `advisor/app/analyzer.py`, a deterministic tool loop (`read_logs`, `filter_records`, `aggregate`, `verify_answer`) that answers only from C2-valid records in the read-only Kong log mount. Citations `[L<id>]` and every summary number are checked against the records loaded for that request; any unsupported result returns the exact C1 fallback `"No verified data"` with `verified=false`. No external LLM or network call is introduced. `/stats` and `/stats/<name>` now expose the same verified aggregate, and Compose sets `ADVISOR_LOG_PATH=/var/log/kong/access.json` on both replicas.

## DEC-017 — Layer 5 terminal evidence 22
- Status: Applied after explicit A/B/C approval for the M5 evidence step
- Decision: Evidence `screenshots/22_layer5_verified_analyzer.png` is a direct screenshot of a visible PowerShell window captured by `scripts/capture-terminal-evidence.ps1` with a new `-Id 22` branch in `scripts/terminal-evidence-run.ps1`. The window shows the 14-test Advisor suite, a verified overview, a verified 429 answer with `[L…]` citations, the exact 503 `"No verified data"` fallback, and the live `/stats` endpoint through Kong. The capture returned `RESULT: PASS`.
