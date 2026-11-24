# Slide source outline — FinTech API Gateway

Deck: `presentation/FinTech_API_Gateway.pptx`  
Builder: `python scripts/build_presentation.py`  
Language: English  
Slides: 24

The builder writes native OOXML with the Python standard library. It was validated by unzipping, parsing every XML part, and opening the file in PowerPoint 2013 (`24 slides`).

## 01 — FinTech API Gateway
- Topic 17, theoretical + practical prototype.
- Reverse proxy edge gateway, declarative DB-less configuration, token-bucket throttling, resiliency.
- Team A Eya Derouiche, B Aya Fayachi, C Wafe Bziouiche.

## 02 — Roadmap
- Core concepts, algorithms, custom diagrams, tools/install, comparison matrix, built system, evidence, AI roadmap.

## 03 — Definitions & core concepts
- API Gateway Pattern: centralised auth, TLS, limits, CORS, logging, routing.
- North-South: client to edge on `:8000` / `:8443`.
- East-West: internal service-to-service traffic.

## 04 — Kong core entities
- Service, Route, Upstream, Target, Consumer, Plugin, mapped to `kong/kong.yml`.

## 05 — Custom diagram 1: plugin pipeline
- `certificate -> rewrite -> access -> header_filter -> body_filter -> log`.
- Our plugins act mainly in `access`, `header_filter` and `log`.

## 06 — Rate-limiting algorithms
- Fixed Window, Sliding Window, Token Bucket, Leaky Bucket.
- Built-in Kong limiter is fixed-window; custom token-bucket plugin is deployed on Payments.

## 07 — Active/passive health checks
- Active `/health` polling every 5 s; passive 5xx/TCP/timeout counting.
- HTTP 429 excluded so rate limiting cannot falsely open the circuit.
- No separate circuit-breaker plugin in this Kong OSS image.

## 08 — Custom diagram 2: ring and state
- Round-robin upstream ring with two weighted targets and `retries=2`.
- `HEALTHY -> UNHEALTHY -> RECOVERED` state transitions.

## 09 — Tools overview
- Kong OSS 3.9.1, Django, FastAPI, Docker Compose, k6/Locust, Prometheus, Alertmanager, n8n, PostgreSQL 16, PyJWT.

## 10 — DB-less installation
- `.env`, Compose config/up, mock smoke tests, `kong config parse`, Admin API reads, DELETE returns 405.

## 11 — DB-less vs PostgreSQL mode
- Source of truth, Admin API, bootstrap, import and best-fit comparison.
- DEC-022: theory only; C4 patched to `0.2.1`; no DB-mode lab claimed.

## 12 — Comparison matrix
- Kong vs Nginx vs Traefik/Envoy across dynamic reload, plugins, L7 auth, L7 rate limiting and footprint.

## 13 — Illustrative built example
- Clients -> Kong -> three Python services -> PostgreSQL, Prometheus, n8n/analyzer.

## 14 — Step 1
- DB-less topology, `_format_version: "3.0"`, three services, three upstreams x two targets.
- Evidence `01`, `02`, `03`.

## 15 — Step 2 auth
- Key-Auth on Accounts/Advisor; JWT on Payments.
- PyJWT only mints demo tokens; Kong validates.
- Evidence `19`.

## 16 — Step 2 plugins
- Tiered rate limiting, token bucket, CORS, request-transformer, correlation-ID, 1 KB guard.
- Evidence `20`, `21`.

## 17 — Step 3 chaos
- k6 2 VUs / 45 s with `accounts-2` stopped.
- `UNHEALTHY -> HEALTHY`, 100% checks, 0% failed requests, Locust cross-check.
- Evidence `24`.

## 18 — Step 4 automation
- `KongCircuitOpen`, `Kong429Spike`, `KongUpstreamTargetUnhealthy`.
- Alertmanager routing/inhibition, three active n8n workflows.
- Evidence `21`, `23`.

## 19 — Step 4 grounded analyzer
- `read_logs -> filter_records -> aggregate -> verify_answer`.
- Citations and exact `"No verified data"` fallback.
- Client-IP stats and 15/15 tests.
- Evidence `22`.

## 20 — AI today and next
- Today: deterministic grounded tool loop, no LLM.
- Approved next: Ollama proposes tool calls; verifier still gates every answer.

## 21 — Contracts and gates
- C1 `0.3.0`, C2 `0.1.1`, C3 `0.2.1`, C4 `0.2.1`.
- Approved PATCHes and no-merge-to-main rule.

## 22 — CI green gate
- P3a, P3b, P3c plus `CI green gate`.
- Runs #23, #24, #25 and #27 green; `main` unchanged.
- Evidence `18`.

## 23 — Evidence gallery
- Formal terminal PNGs `01`, `19`, `20`, `21`, `22`, `23`, `24`, `25`.

## 24 — Final Gate and next
- `PASS WITH WARNINGS`, 54/54 checks.
- Open warnings: evidence `10`, `11`, `13`, `14`, spike record, Telegram credentials, branch-protection re-read.
- Immediate next: approved Ollama hybrid, contracts unchanged.

## Rebuild

```powershell
python scripts\build_presentation.py
```

To verify in PowerPoint:

```powershell
$app = New-Object -ComObject PowerPoint.Application
$pres = $app.Presentations.Open('presentation\FinTech_API_Gateway.pptx', $true, $false, $false)
$pres.Slides.Count   # 24
$pres.Close()
$app.Quit()
```
