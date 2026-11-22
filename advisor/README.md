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
