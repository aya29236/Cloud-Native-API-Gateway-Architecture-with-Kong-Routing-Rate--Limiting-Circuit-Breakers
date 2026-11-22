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