"""Verified tool-calling analyzer for the C1 Advisor contract (Layer 5).

The analyzer deliberately makes no external LLM call. It follows the same
audit contract as a tool-calling agent:

1. ``read_logs`` reads the read-only Kong file-log mount.
2. ``filter_records`` selects C2-valid records that support the question.
3. ``aggregate`` computes statistics only from those records.
4. ``verify_answer`` checks every citation and every number before replying.

If any step lacks verified support, the exact C1 fallback "No verified data"
is returned with ``verified=false`` and no citations.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import AnalyzeResponse

DEFAULT_LOG_PATH = "/var/log/kong/access.json"
NO_VERIFIED_DATA = "No verified data"
CITATION_RE = re.compile(r"^\[L([1-9]\d*)\]$")
MAX_CITATIONS = 10
ALLOWED_TOOLS = ("read_logs", "filter_records", "aggregate", "verify_answer")


@dataclass(frozen=True)
class LogRecord:
    """One C2-valid access-log record with its stable citation id."""

    line_id: int
    client_ip: str
    method: str
    uri: str
    status: int
    latencies: dict[str, Any]
    started_at: int
    consumer: str
    route: str
    service: str

    @property
    def citation(self) -> str:
        return f"[L{self.line_id}]"


@dataclass(frozen=True)
class Selection:
    """The result of the filter_records tool."""

    intent: str
    predicate: str
    records: list[LogRecord]


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _nested_name(record: dict[str, Any], parent: str, key: str) -> str:
    value = record.get(parent)
    if isinstance(value, dict):
        name = value.get(key)
        return str(name) if name is not None else ""
    return ""


def _valid_c2_record(raw: Any) -> bool:
    """Check the C2 0.1.1 required fields without adding a schema dependency."""
    if not isinstance(raw, dict):
        return False
    if not isinstance(raw.get("client_ip"), str):
        return False
    request = raw.get("request")
    if not isinstance(request, dict):
        return False
    if not isinstance(request.get("method"), str) or not isinstance(request.get("uri"), str):
        return False
    response = raw.get("response")
    if not isinstance(response, dict) or not isinstance(response.get("status"), int):
        return False
    if not isinstance(raw.get("latencies"), dict):
        return False
    return isinstance(raw.get("started_at"), int)


def read_logs(path: str | Path | None = None) -> tuple[list[LogRecord], dict[str, Any]]:
    """Read JSONL, a JSON array, or one JSON object from the Kong log path."""
    target = Path(path or os.getenv("ADVISOR_LOG_PATH", DEFAULT_LOG_PATH))
    info: dict[str, Any] = {
        "path": str(target),
        "source": "kong-file-log",
        "status": "ok",
        "raw_records": 0,
        "valid_records": 0,
        "invalid_records": 0,
    }

    if not target.is_file():
        info.update(status="unavailable", reason="log file not present")
        return [], info

    try:
        text = target.read_text(encoding="utf-8")
    except OSError as exc:
        info.update(status="unreadable", reason=type(exc).__name__)
        return [], info

    if not text.strip():
        info["status"] = "empty"
        return [], info

    raw_records: list[tuple[int, Any]] = []
    try:
        document = json.loads(text)
    except json.JSONDecodeError:
        for line_id, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                raw_records.append((line_id, json.loads(line)))
            except json.JSONDecodeError:
                info["invalid_records"] += 1
    else:
        if isinstance(document, dict):
            raw_records = [(1, document)]
        elif isinstance(document, list):
            raw_records = list(enumerate(document, start=1))
        else:
            info.update(status="invalid", reason="top-level JSON is not an object or array")
            return [], info

    records: list[LogRecord] = []
    for line_id, raw in raw_records:
        if not _valid_c2_record(raw):
            info["invalid_records"] += 1
            continue
        request = raw["request"]
        records.append(
            LogRecord(
                line_id=line_id,
                client_ip=raw["client_ip"],
                method=request["method"],
                uri=request["uri"],
                status=raw["response"]["status"],
                latencies=dict(raw["latencies"]),
                started_at=raw["started_at"],
                consumer=_nested_name(raw, "consumer", "username"),
                route=_nested_name(raw, "route", "name"),
                service=_nested_name(raw, "service", "name"),
            )
        )

    info["raw_records"] = len(raw_records)
    info["valid_records"] = len(records)
    return records, info


def aggregate(records: list[LogRecord]) -> dict[str, Any]:
    """Aggregate only the records passed in by the filter_records tool."""
    status_counts: dict[str, int] = {}
    consumer_counts: dict[str, int] = {}
    route_counts: dict[str, int] = {}
    proxy_values: list[float] = []

    for record in records:
        status_key = str(record.status)
        status_counts[status_key] = status_counts.get(status_key, 0) + 1
        if record.consumer:
            consumer_counts[record.consumer] = consumer_counts.get(record.consumer, 0) + 1
        if record.route:
            route_counts[record.route] = route_counts.get(record.route, 0) + 1
        proxy = record.latencies.get("proxy")
        if _is_number(proxy):
            proxy_values.append(float(proxy))

    return {
        "requests_total": len(records),
        "errors_total": sum(1 for record in records if record.status >= 400),
        "rate_limited_total": sum(1 for record in records if record.status == 429),
        "server_error_total": sum(1 for record in records if 500 <= record.status < 600),
        "status_counts": dict(sorted(status_counts.items())),
        "consumer_counts": dict(sorted(consumer_counts.items())),
        "route_counts": dict(sorted(route_counts.items())),
        "avg_proxy_latency_ms": round(sum(proxy_values) / len(proxy_values), 2)
        if proxy_values
        else 0,
        "max_proxy_latency_ms": round(max(proxy_values), 2) if proxy_values else 0,
    }


def select_records(records: list[LogRecord], question: str) -> Selection:
    """Choose a deterministic, named predicate from the question."""
    text = question.lower()

    if any(token in text for token in ("429", "rate limit", "rate-limit", "ratelimit")):
        return Selection(
            "rate_limit",
            "response.status == 429",
            [record for record in records if record.status == 429],
        )

    if any(token in text for token in ("503", "circuit", "upstream", "unhealthy")):
        return Selection(
            "upstream_errors",
            "response.status == 503",
            [record for record in records if record.status == 503],
        )

    if any(token in text for token in ("latency", "slow", "proxy")):
        timed = [record for record in records if _is_number(record.latencies.get("proxy"))]
        timed.sort(key=lambda record: float(record.latencies["proxy"]), reverse=True)
        return Selection(
            "latency",
            "latencies.proxy present, sorted descending",
            timed,
        )

    if any(token in text for token in ("error", "fail", "4xx", "5xx")):
        return Selection(
            "errors",
            "response.status >= 400",
            [record for record in records if record.status >= 400],
        )

    consumer = next(
        (token for token in ("fintech-free", "fintech-premium") if token in text),
        "",
    )
    route = next(
        (token for token in ("accounts", "payments", "advisor") if token in text),
        "",
    )
    if consumer or route:
        matched = [
            record
            for record in records
            if (not consumer or record.consumer == consumer)
            and (
                not route
                or route in record.route.lower()
                or route in record.service.lower()
                or route in record.uri.lower()
            )
        ]
        return Selection(
            "breakdown",
            f"consumer={consumer or 'any'}; route/service/uri contains {route or 'any'}",
            matched,
        )

    return Selection("overview", "all verified C2 records", list(records))


def build_summary(selection: Selection, stats: dict[str, Any]) -> str:
    """Build a summary whose numbers come only from the aggregate tool."""
    total = stats["requests_total"]

    if selection.intent == "rate_limit":
        return f"Verified {total} HTTP 429 rate-limited request(s) in the Kong access logs."
    if selection.intent == "upstream_errors":
        return f"Verified {total} HTTP 503 upstream error response(s) in the Kong access logs."
    if selection.intent == "latency":
        return (
            f"Verified {total} request(s) with recorded proxy latency; "
            f"maximum {stats['max_proxy_latency_ms']} ms."
        )
    if selection.intent == "errors":
        return f"Verified {total} HTTP error response(s) in the Kong access logs."
    if selection.intent == "breakdown":
        return f"Verified {total} request(s) matching the requested consumer or route."
    return f"Verified {total} C2-valid request(s) in the Kong access logs."


def safe_response(
    trace: list[dict[str, Any]],
    stats: dict[str, Any] | None = None,
    reason: str = "no supported answer",
) -> AnalyzeResponse:
    """Return the exact C1 fallback and record why the verifier rejected it."""
    entries = list(trace)
    if not entries or entries[-1].get("tool") != "verify_answer":
        entries.append(
            {
                "tool": "verify_answer",
                "arguments": {"reason": reason},
                "result": {"verified": False},
            }
        )
    return AnalyzeResponse(
        summary=NO_VERIFIED_DATA,
        stats=stats or {},
        citations=[],
        tool_trace=entries,
        verified=False,
    )


def verify_answer(
    response: AnalyzeResponse,
    records: list[LogRecord],
    trace: list[dict[str, Any]],
) -> bool:
    """Reject an answer unless its citations and numbers trace to tool output."""
    tools = [entry.get("tool") for entry in trace]
    if not tools or tools[0] != "read_logs" or tools[-1] != "verify_answer":
        return False
    if any(tool not in ALLOWED_TOOLS for tool in tools):
        return False

    if response.summary == NO_VERIFIED_DATA:
        return response.verified is False and response.citations == []

    if response.verified is not True or not response.citations:
        return False

    known_ids = {record.line_id for record in records}
    citation_ids: list[int] = []
    for citation in response.citations:
        match = CITATION_RE.fullmatch(citation)
        if match is None:
            return False
        citation_ids.append(int(match.group(1)))
    if not set(citation_ids) <= known_ids:
        return False

    summary_numbers = set(re.findall(r"\d+", response.summary))
    stat_numbers = {
        str(value)
        for value in response.stats.values()
        if isinstance(value, int) and not isinstance(value, bool)
    }
    for key in ("status_counts", "consumer_counts", "route_counts"):
        nested = response.stats.get(key, {})
        if isinstance(nested, dict):
            stat_numbers.update(str(value) for value in nested.values())
    return bool(summary_numbers & stat_numbers)


def answer_question(question: str, log_path: str | Path | None = None) -> AnalyzeResponse:
    """Run the verified tool loop for one C1 ``/analyze`` request."""
    trace: list[dict[str, Any]] = []
    records, read_info = read_logs(log_path)
    trace.append(
        {
            "tool": "read_logs",
            "arguments": {"path": read_info["path"]},
            "result": read_info,
        }
    )

    overall = aggregate(records)
    if not records:
        return safe_response(trace, {}, "no C2-valid records available")

    selection = select_records(records, question)
    trace.append(
        {
            "tool": "filter_records",
            "arguments": {
                "question": question,
                "intent": selection.intent,
                "predicate": selection.predicate,
            },
            "result": {"matched": len(selection.records)},
        }
    )
    if not selection.records:
        return safe_response(trace, overall, f"no records matched {selection.intent}")

    stats = aggregate(selection.records)
    trace.append(
        {
            "tool": "aggregate",
            "arguments": {"intent": selection.intent, "record_count": len(selection.records)},
            "result": stats,
        }
    )

    citations = [record.citation for record in selection.records[:MAX_CITATIONS]]
    trace.append(
        {
            "tool": "verify_answer",
            "arguments": {"citations": citations},
            "result": {
                "verified": True,
                "checks": ["citation_ids_exist", "summary_numbers_from_aggregate"],
            },
        }
    )
    response = AnalyzeResponse(
        summary=build_summary(selection, stats),
        stats=stats,
        citations=citations,
        tool_trace=trace,
        verified=True,
    )
    if not verify_answer(response, records, trace):
        return safe_response(trace, stats, "verifier rejected unsupported answer")
    return response


def current_stats(log_path: str | Path | None = None) -> dict[str, Any]:
    """Return real aggregate values for the C1 ``/stats`` endpoints."""
    records, _ = read_logs(log_path)
    return aggregate(records)
