"""Bounded raw LLM tool-calling loop for AI1 deterministic tools."""

import json
import re
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from advisor.ai1.models import ParsedLogRecord
from .llm import LLMClient
from .prompts import SYSTEM_PROMPT, tool_result_message
from .schemas import TOOL_REGISTRY, build_tool_definitions


MAX_STEPS = 6
CITATION_RE = re.compile(r"\[L([1-9][0-9]*)\]")


class AnalyzeResponse(BaseModel):
    """C1 analyzer response shape."""

    model_config = ConfigDict(extra="forbid")

    summary: str
    stats: dict[str, Any]
    citations: list[str]
    tool_trace: list[dict[str, Any]]
    verified: bool = False


def _tool_call_parts(call: Mapping[str, Any]) -> tuple[str, Any]:
    function = call.get("function")
    if not isinstance(function, Mapping):
        return "", {}
    name = function.get("name")
    arguments = function.get("arguments", {})
    return str(name or ""), arguments


def _arguments_dict(arguments: Any) -> dict[str, Any]:
    if isinstance(arguments, Mapping):
        return dict(arguments)
    if isinstance(arguments, str):
        try:
            parsed = json.loads(arguments)
            return dict(parsed) if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def analyze(
    question: str,
    records: Sequence[ParsedLogRecord],
    client: LLMClient,
    max_steps: int = MAX_STEPS,
) -> AnalyzeResponse:
    """Run a bounded raw tool-calling loop over read-only AI1 records."""
    if isinstance(max_steps, bool) or not isinstance(max_steps, int) or max_steps < 1:
        return AnalyzeResponse(
            summary="No verified data",
            stats={},
            citations=[],
            tool_trace=[{"step": 0, "tool": "", "arguments": {}, "result_summary": "", "error": "invalid max_steps"}],
        )

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    tools = build_tool_definitions()
    tool_trace: list[dict[str, Any]] = []
    stats: dict[str, Any] = {}
    answer = ""

    for loop_step in range(1, max_steps + 1):
        try:
            assistant = client.chat(messages, tools)
        except Exception as exc:
            return AnalyzeResponse(
                summary="No verified data",
                stats=stats,
                citations=[],
                tool_trace=tool_trace
                + [
                    {
                        "step": loop_step,
                        "tool": "",
                        "arguments": {},
                        "result_summary": "",
                        "error": f"LLM error: {exc}",
                    }
                ],
            )

        tool_calls = assistant.get("tool_calls")
        if not isinstance(tool_calls, list) or not tool_calls:
            answer = assistant.get("content")
            answer = answer.strip() if isinstance(answer, str) else ""
            break

        for call in tool_calls:
            step = len(tool_trace) + 1
            if step > max_steps:
                return AnalyzeResponse(
                    summary="No verified data",
                    stats=stats,
                    citations=[],
                    tool_trace=tool_trace
                    + [
                        {
                            "step": step,
                            "tool": "",
                            "arguments": {},
                            "result_summary": "",
                            "error": "step cap reached",
                        }
                    ],
                )

            tool_name, raw_arguments = _tool_call_parts(call)
            arguments = _arguments_dict(raw_arguments)
            error = ""
            result: Any = None
            result_summary = ""

            if tool_name not in TOOL_REGISTRY:
                error = f"unknown tool: {tool_name}"
                tool_trace.append(
                    {
                        "step": step,
                        "tool": tool_name,
                        "arguments": arguments,
                        "result_summary": "",
                        "error": error,
                    }
                )
                messages.append(
                    tool_result_message(
                        tool_name,
                        {"error": error},
                    )
                )
                continue

            argument_model, tool = TOOL_REGISTRY[tool_name]
            try:
                validated = argument_model.model_validate(arguments)
                kwargs = validated.model_dump()
                result = tool(records, **kwargs)
                stats[tool_name] = result
                result_summary = json.dumps(result, ensure_ascii=False, sort_keys=True)[:500]
            except (ValidationError, ValueError, TypeError) as exc:
                error = f"invalid arguments: {exc}"
                result_summary = ""
                if isinstance(exc, ValidationError):
                    error = f"invalid arguments: {exc.errors(include_url=False)}"

            tool_trace.append(
                {
                    "step": step,
                    "tool": tool_name,
                    "arguments": arguments,
                    "result_summary": result_summary,
                    "error": error,
                }
            )
            messages.append(
                tool_result_message(
                    tool_name,
                    result if not error else {"error": error},
                )
            )
    else:
        answer = "No verified data"

    if not answer:
        answer = "No verified data"

    citations = sorted(set(f"[L{number}]" for number in CITATION_RE.findall(answer)))
    return AnalyzeResponse(
        summary=answer,
        stats=stats,
        citations=citations,
        tool_trace=tool_trace,
        verified=False,  # TODO(AI3): replace with verifier result.
    )


def save_trace(response: AnalyzeResponse, directory: str = "advisor/traces") -> Path:
    """Save one JSON trace file with timestamp and question slug."""
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc)
    stamp = timestamp.strftime("%Y%m%dT%H%M%S%fZ")
    summary = response.summary.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", summary).strip("-")[:60] or "trace"
    path = target / f"{stamp}-{slug}.json"
    payload = {
        "timestamp": timestamp.isoformat(),
        "response": response.model_dump(),
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path
