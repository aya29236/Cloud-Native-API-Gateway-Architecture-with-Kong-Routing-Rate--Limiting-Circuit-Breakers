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

## Student C AI2

AI2 is a bounded tool-calling loop that uses Pydantic-generated Ollama tool
schemas and deterministic AI1 tools. It has no agent framework or fine-tuning.

Set the Ollama model explicitly:

```powershell
$env:OLLAMA_HOST = "http://localhost:11434"
$env:ADVISOR_MODEL = "<your-installed-tool-capable-model>"
```

`OLLAMA_HOST` defaults to `http://localhost:11434`. `ADVISOR_MODEL` has no
default; it must be set before `OllamaClient` can start.

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
preserves ordered traces. It never computes statistics. `AnalyzeResponse.verified`
is always `False`; AI3 will perform verification and retry.

## Student C AI3

AI3 is a deterministic verifier over AI2 tool traces. It extracts IPs, routes,
numeric values and `[L<id>]` citations, then checks only evidence produced by the
tools called in the current run. Numeric values in tool arguments, including limits
and time bounds, are also allowed evidence.

The verifier does not inspect the raw log file or the original question. It does
not check every possible semantic fact, sentence style or whether an answer is
complete. It does block unsupported IPs, routes, numbers and citation claims.

A failed answer gets one retry. The first and retry attempts share a maximum
tool-call budget of six. If the retry fails, the delivered summary is exactly
`No verified data`.

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
