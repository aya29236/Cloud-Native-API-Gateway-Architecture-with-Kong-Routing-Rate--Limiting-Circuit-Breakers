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
- [x] Contract drafts C1–C4 (v0.1.0; require approval by all three students)
- [x] Sample Kong access-log fixture
- [x] Fake Alertmanager payload fixture
- [x] Mock upstream with `/health`, `/echo`, `/fail`, `/slow`
- [x] Compose skeleton and core profile
- [ ] CI workflow and repository branch protection
- [ ] All three students approve contracts
- [ ] LLM tool-calling spike completed by all three
- [ ] Open questions sent to professor

## Contract change rule
Contracts are versioned independently. Any breaking change requires a MAJOR version bump and approval from A, B and C. Backward-compatible additions require a MINOR bump. Editorial corrections require a PATCH bump. Record every accepted change in `decisions.md`.

## Important
C1–C4 in this starter are proposed v0.1.0 drafts based on the project master plan. Treat them as review candidates, not as approved specifications, until all three students confirm them. Kong's actual access-log fields and Prometheus metric names must be checked against the running `kong:3.9.1` image before being frozen.
