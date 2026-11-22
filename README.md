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

## Gate 0 status
- [x] Initial repository layout
- [x] Contracts C1–C4 approved and frozen by all three students (C1 v0.3.0, C2 v0.1.1, C3/C4 v0.2.0)
- [x] Sample Kong access-log fixture
- [x] Fake Alertmanager payload fixture
- [x] Mock upstream with `/health`, `/echo`, `/fail`, `/slow`
- [x] Compose skeleton and core profile
- [ ] CI workflow and repository branch protection
- [x] All three students approve contracts
- [ ] LLM tool-calling spike completed by all three
- [ ] Open questions sent to professor

## Contract change rule
Contracts are versioned independently. Any breaking change requires a MAJOR version bump and approval from A, B and C. Backward-compatible additions require a MINOR bump. Editorial corrections require a PATCH bump. Record every accepted change in `decisions.md`.

## Important
C1–C4 are approved and frozen by all three students and are the specifications the services implement. Live verification is still required at G7 (Kong access-log fields vs C2) and M1 (Prometheus metric names vs C3); a mismatch is handled by an approved, versioned contract change.
