# Architecture decisions

## DEC-001 — Contract-first integration
- Status: Proposed
- Decision: C1–C4 are versioned contracts. Services, Kong configuration, monitoring and the analyzer implement these contracts rather than inventing independent formats.
- Approval required: Student A, Student B, Student C.

## DEC-002 — Kong deployment mode
- Status: Accepted from master plan
- Decision: Use Kong Open Source 3.9.1 in DB-less mode with declarative `kong.yml`.

## DEC-003 — Gate 0 mock upstream
- Status: Proposed
- Decision: Provide deterministic `/health`, `/echo`, `/fail`, and `/slow` endpoints for integration work before real services exist.