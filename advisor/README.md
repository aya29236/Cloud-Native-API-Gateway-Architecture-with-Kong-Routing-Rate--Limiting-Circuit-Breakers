# Student C AI1

AI1 is an isolated, read-only reader and deterministic analyzer for the proposed C2
Kong access-log format. It does not call an LLM or FastAPI and does not write Kong
logs.

## Install

From the repository root:

```powershell
python -m pip install -r advisor/requirements-ai1.txt
```

Pydantic v2 validates records. pytest runs tests. pandas is test-only and is not
used by the runtime implementation.

## Test

```powershell
python -m pytest advisor/tests/test_ai1.py -q
python -m pytest advisor/tests -v
```

## Demo

```powershell
python -m advisor.ai1.demo
```

## Supported formats

- One complete JSON object, including a pretty-printed object.
- JSONL with one JSON object per physical line.
- Blank and malformed physical lines are counted separately and never enter tools.
- Multiple/mixed pretty-printed objects are unsupported and are reported as
  malformed instead of silently discarded.

## Provisional assumptions

- Missing, null and empty consumer usernames aggregate as `anonymous`.
- Route grouping uses `route.name` when populated and otherwise falls back to
  `request.uri`. Empty route names do not mutate the original record.
- Valid records receive physical source IDs as `L<line_number>`.
- `started_at` remains an integer. Its unit and timezone are unconfirmed.
- Counts use descending count order, with ascending string tie-breaking.
- Time bounds are inclusive and integer-valued.
- `top_ips`, `top_routes`, `top_ip_route_pairs` and `consumer_stats` accept an
  optional `status` filter from 100 through 599. The filter combines with the
  inclusive time window; when omitted, the previous all-status behavior is
  unchanged. Invalid direct-tool values raise `ValueError`, surfaced as HTTP
  422 by the stats API.

## Student C AI2

AI2 is a bounded tool-calling loop that uses Pydantic-generated Ollama tool
schemas and deterministic AI1 tools. It has no agent framework or fine-tuning.

Set the Ollama model explicitly:

```powershell
$env:OLLAMA_HOST = "http://localhost:11434"
$env:ADVISOR_MODEL = "<your-installed-tool-capable-model>"
$env:OLLAMA_TIMEOUT = "180"
```

`OLLAMA_HOST` defaults to `http://localhost:11434`. `ADVISOR_MODEL` has no
default; it must be set before `OllamaClient` can start. `OLLAMA_TIMEOUT` is the
request timeout in seconds and defaults to 180; a timeout returns an explicit
error instead of an answer.

Run the no-network scripted demo:

```powershell
python -m advisor.ai2.demo
```

Run the real Ollama spike:

```powershell
python -m advisor.ai2.spike
```

The live demo is available when the model is configured:

```powershell
python -m advisor.ai2.demo --live
```

AI2 only sends tool arguments to AI1, wraps tool output as untrusted data, and
preserves ordered traces. It never computes statistics. Repeated identical calls
reuse the prior result and tell the model to answer rather than repeat the call.

## Student C AI3

AI3 is a deterministic verifier over AI2 tool traces. It extracts IPs, routes,
numeric values and `[L<id>]` citations, then checks only evidence produced by the
tools called in the current run. Numeric values in tool arguments are evidence
only when the arguments pass the registered tool schema and the trace has no
error. Numbers in the original question are not evidence.

The verifier does not inspect the raw log file or the original question. It does
not check every possible semantic fact, sentence style or whether an answer is
complete. It does block unsupported IPs, routes, numbers and citation claims.

A failed answer gets one retry. The first and retry attempts share a maximum
tool-call budget of six. A summary equal to `No verified data` after trimming
whitespace and removing at most one trailing period is normalized to exactly
`No verified data`.

The verifier strips trailing punctuation from route tokens before exact evidence
matching (so `/api/payments.` matches evidence for `/api/payments`, but
`/api/payments.x` does not). **This is the only change in this set that makes
verification more permissive**; the period is treated as sentence punctuation,
while internal route dots remain part of the token.

`verified=True` means that the delivered summary passed the deterministic verifier.
If both generated answers fail, the delivered `No verified data` fallback itself
passes verification and is returned with `verified=True`; both rejected reports
and `fallback=true` are retained in the saved trace. **Pending team approval of the
C1 meaning of `verified`.** AI3 does not replace an independent semantic judge.

Run the script-measuring verifier evaluation:

```powershell
python -m advisor.ai3.evaluate
```

The scripted table is written to `advisor/ai3/eval_table.md`. Scripted mode measures
the verifier, not a real LLM. Live mode requires an explicit model:

```powershell
$env:ADVISOR_MODEL = "<your-installed-tool-capable-model>"
$env:OLLAMA_HOST = "http://localhost:11434"
python -m advisor.ai3.evaluate --live
```

The live table is written to `advisor/ai3/eval_table_live.md`. Live mode sends only
the question text and does not use the committed scripted answers.
Each live question also saves its tool trace and verifier reports under
`advisor/traces/live/`; generated trace JSON files are ignored by Git.

The evaluation questions informed the prompt and tool changes, so the live table
is a **development set, not an independent test set**. “Invented facts BLOCKED”
counts questions whose first-attempt verifier report contains an unsupported
fact and whose delivered answer passes the verifier, in both scripted and live
modes.

## Live evaluation comparison

| Run | Model / trace status | Exact-match | Invented facts BLOCKED | Notes |
|---|---|---:|---:|---|
| Run 1 | qwen2.5:7b; no per-question traces saved | 1/10 | 0 | Pre-fix result preserved in `advisor/ai3/eval_table_live_run1.md`. |
| Run 2 | qwen2.5:7b; 18 per-question traces saved | 8/10 | 2 | Post-fix run; per-question causes are summarized below. |

Run 1 failures visible in the table: G03/G04 had correct count information but
the old substring comparator rejected the model's labeled formatting. C01's
`/api/payments.` was rejected because punctuation was not stripped. P04/G01
reported unsupported `429`; without their traces, it is not possible to confirm
whether the model omitted a status filter or the call failed. P01/P02/G02/G05
delivered refusals without traces, so their underlying causes cannot be
reconstructed; P02's trailing period also failed the exact refusal comparison.
H02 showed an invented IP in the failure column while the live blocked metric
still reported zero.

Run 2 remaining exact-match failures, checked against the saved traces:

- **G05:** `time_range` returned records labeled L16-L19, but the answer cited
  those IDs and the verifier only accepts citation IDs returned by
  `get_log_lines`. Both attempts were rejected for unsupported citations, so the
  verified fallback was delivered.
- **C01:** `get_log_lines` returned L1, but the answer paraphrased the request
  instead of quoting `GET /api/payments` and omitted `[L1]`; it passed fact
  verification but failed the structured exact-request comparator.
- **S01:** the model called `get_log_lines` and `status_breakdown`, then supplied
  a supported status summary instead of the exact refusal expected by the
  step-cap case. The trailing `No verified data.` did not make the whole answer
  an exact refusal.

## Local FastAPI

Install the API dependencies from the repository root and start the standalone
app:

```powershell
python -m pip install -r advisor/requirements-api.txt
uvicorn advisor.api.app:app --reload
```

Swagger UI is available at `http://127.0.0.1:8000/docs`; `GET /health` reports
whether requests use `synthetic` or `kong-log` data. If `KONG_LOG_PATH` is unset
or points to a missing file, this local app creates a seeded synthetic JSONL file
in the system temporary directory for its lifetime. Otherwise it reads the
configured Kong log. The reusable stats router itself returns HTTP 503 when its
configured log file is unavailable.

Configuration:

- `KONG_LOG_PATH`: access-log path; defaults to `/var/log/kong/access.json` for
  the reusable router.
- `OLLAMA_HOST`: Ollama base URL; defaults to `http://localhost:11434`.
- `ADVISOR_MODEL`: required Ollama model name for `POST /analyze`.

Aya can include the routers in her existing FastAPI shell without changing it:

```python
from advisor.api import analyze_router, stats_router

app.include_router(stats_router)
app.include_router(analyze_router)
```

When running in Docker, set `OLLAMA_HOST` to a hostname reachable from the
container, such as the host gateway or the Ollama service name; `localhost`
inside the API container refers to that container itself.

`GET /stats/*` endpoints invoke only read-only deterministic AI1 tools and do
not use an LLM. `/analyze` returns the existing C1 fields and uses AI3
verification; unavailable or unconfigured Ollama service/model errors return
HTTP 503 rather than a fabricated answer.
