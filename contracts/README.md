# Contract pack — README v0.1.0

The version in this heading belongs to this README file only. It does not track the individual contract versions; each contract file carries its own `version` or `contract_version`.

All four contracts are **approved and frozen** by Student A (Eya Derouiche), Student B (Aya Fayachi) and Student C (Wafe Bziouiche) at Gate 0. Services, Kong configuration, monitoring and the analyzer implement these contracts rather than inventing independent formats.

| Contract | File | Version | Status | Purpose |
|---|---|---|---|---|
| C1 | `api/openapi.yml` | 0.3.0 | Approved | Service HTTP interfaces |
| C2 | `logs/kong-access-log.schema.json` | 0.1.1 | Approved | Analyzer-facing Kong access-log record |
| C3 | `metrics/alerts-contract.yml` | 0.2.0 | Approved | Alert names, rules and webhook payload |
| C4 | `naming/environment.yml` | 0.2.0 | Approved | Names, ports, profiles and shared environment |

## Versioning

- MAJOR: breaking changes.
- MINOR: backward-compatible additions.
- PATCH: editorial or non-functional corrections.

Record decisions in the repository root `decisions.md`.

Any contract change must be submitted through a pull request, with a version bump and contract tests rerun by consumers.

## Verification qualifications

Approval at Gate 0 does not replace live verification. G7 checks the real Kong 3.9.1 file-log fields against C2, and M1 checks the real `/metrics` names against C3. If either differs, the contract is changed by an approved, versioned pull request and every consumer reruns its contract tests.
