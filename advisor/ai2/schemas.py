"""Pydantic-generated Ollama tool schemas and the AI1 tool registry."""

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from advisor.ai1.tools import (
    ConsumerStatsArgs,
    GetLogLinesArgs,
    StatusBreakdownArgs,
    TimeRangeArgs,
    TopIPRoutePairsArgs,
    TopIPsArgs,
    TopRoutesArgs,
    consumer_stats,
    get_log_lines,
    status_breakdown,
    time_range,
    top_ip_route_pairs,
    top_ips,
    top_routes,
)


DESCRIPTIONS: dict[str, str] = {
    "time_range": "Read-only: return valid Kong log records inside an inclusive integer started_at range.",
    "status_breakdown": "Read-only: count HTTP response statuses, optionally inside an integer time range.",
    "top_ips": "Read-only: count and rank client IPs deterministically; only count records with this HTTP status when status is supplied.",
    "top_routes": "Read-only: count and rank route names, with request URI fallback; only count records with this HTTP status when status is supplied.",
    "top_ip_route_pairs": "Read-only: count and rank client IP and route pairs; only count records with this HTTP status when status is supplied.",
    "consumer_stats": "Read-only: count Kong consumers, treating missing, null or empty usernames as anonymous; only count records with this HTTP status when status is supplied.",
    "get_log_lines": "Read-only: return at most 20 log records in physical line-ID order for citation.",
}


def build_tool_definitions() -> list[dict[str, Any]]:
    """Build Ollama /api/chat function definitions from Pydantic models."""
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": model.model_json_schema(),
            },
        }
        for name, model, description in (
            ("time_range", TimeRangeArgs, DESCRIPTIONS["time_range"]),
            ("status_breakdown", StatusBreakdownArgs, DESCRIPTIONS["status_breakdown"]),
            ("top_ips", TopIPsArgs, DESCRIPTIONS["top_ips"]),
            ("top_routes", TopRoutesArgs, DESCRIPTIONS["top_routes"]),
            ("top_ip_route_pairs", TopIPRoutePairsArgs, DESCRIPTIONS["top_ip_route_pairs"]),
            ("consumer_stats", ConsumerStatsArgs, DESCRIPTIONS["consumer_stats"]),
            ("get_log_lines", GetLogLinesArgs, DESCRIPTIONS["get_log_lines"]),
        )
    ]


TOOL_REGISTRY: dict[str, tuple[type[BaseModel], Callable[..., Any]]] = {
    "time_range": (TimeRangeArgs, time_range),
    "status_breakdown": (StatusBreakdownArgs, status_breakdown),
    "top_ips": (TopIPsArgs, top_ips),
    "top_routes": (TopRoutesArgs, top_routes),
    "top_ip_route_pairs": (TopIPRoutePairsArgs, top_ip_route_pairs),
    "consumer_stats": (ConsumerStatsArgs, consumer_stats),
    "get_log_lines": (GetLogLinesArgs, get_log_lines),
}
