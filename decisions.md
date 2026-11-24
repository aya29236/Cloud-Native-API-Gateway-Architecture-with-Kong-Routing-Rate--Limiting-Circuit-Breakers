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
- Decision: Replace the Gate 0 CI skeleton with three real jobs (P3a repository checks, P3b pytest/Kong/plugin mocks, P3c amtool/promtool/verifier/image builds) plus one aggregate green gate. The fragment merger is rewritten with the Python standard library so CI does not depend on PyYAML, which the project owner explicitly rejected. The pipeline runs on every push, pull request and manual dispatch. Evidence 18 was captured from real Actions runs #9 (red: broken `kong.yml`) and #10 (green: restored `kong.yml`); branch protection is still to be configured on GitHub.

## DEC-010 — Verified lab toolchain and G6 byte limit
- Status: Applied after the A/B/C approval following evidence 18
- Decision: `scripts/make_jwt.py` uses real PyJWT 2.15.1 pinned in `requirements-dev.txt` instead of hand-rolled HS256. `scripts/gen_keys.sh` and `scripts/gen_cert.sh` require real GNU bash and OpenSSL from Git for Windows, fail loudly when absent, and handle MSYS path conversion. `kong/fragments/30-transform.yml` sets `allowed_payload_size: 1024` with `size_unit: bytes` so the documented 1 KB `request-size-limiting` behavior is real. The G2–G7 live redo passed 25/25 checks against the Gate 0 mock upstream; the transcript is in `tests/fragments/independent-wave-results.txt`.
