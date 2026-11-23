"""Small, read-only deterministic tools over parsed Kong access logs."""

from collections import Counter
from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .models import ParsedLogRecord


class ToolArgumentModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class TimeRangeArgs(ToolArgumentModel):
    start_at: int | None = None
    end_at: int | None = None


class StatusBreakdownArgs(ToolArgumentModel):
    start_at: int | None = None
    end_at: int | None = None


class TopIPsArgs(ToolArgumentModel):
    limit: int = 10
    start_at: int | None = None
    end_at: int | None = None
    status: int | None = Field(
        default=None,
        ge=100,
        le=599,
        description="Only count records with this HTTP status.",
    )


class TopRoutesArgs(ToolArgumentModel):
    limit: int = 10
    start_at: int | None = None
    end_at: int | None = None
    status: int | None = Field(
        default=None,
        ge=100,
        le=599,
        description="Only count records with this HTTP status.",
    )


class TopIPRoutePairsArgs(ToolArgumentModel):
    limit: int = 10
    start_at: int | None = None
    end_at: int | None = None
    status: int | None = Field(
        default=None,
        ge=100,
        le=599,
        description="Only count records with this HTTP status.",
    )


class ConsumerStatsArgs(ToolArgumentModel):
    start_at: int | None = None
    end_at: int | None = None
    status: int | None = Field(
        default=None,
        ge=100,
        le=599,
        description="Only count records with this HTTP status.",
    )


class GetLogLinesArgs(ToolArgumentModel):
    limit: int = 20


def _records(
    records: Iterable[ParsedLogRecord],
) -> list[ParsedLogRecord]:
    return list(records)


def _validate_bounds(start_at: int | None, end_at: int | None) -> None:
    for name, value in (("start_at", start_at), ("end_at", end_at)):
        if value is not None:
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{name} must be an integer")
    if start_at is not None and end_at is not None and start_at > end_at:
        raise ValueError("start_at must be less than or equal to end_at")


def _validate_limit(limit: int) -> None:
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise ValueError("limit must be an integer")
    if limit < 0:
        raise ValueError("limit must be non-negative")


def _validate_status(status: int | None) -> None:
    if status is None:
        return
    if isinstance(status, bool) or not isinstance(status, int):
        raise ValueError("status must be an integer")
    if not 100 <= status <= 599:
        raise ValueError("status must be between 100 and 599")


def _filter_time(
    records: Iterable[ParsedLogRecord],
    start_at: int | None = None,
    end_at: int | None = None,
    status: int | None = None,
) -> list[ParsedLogRecord]:
    """Filter on inclusive integer ``started_at`` bounds."""
    return [
        item
        for item in records
        if (start_at is None or item.record.started_at >= start_at)
        and (end_at is None or item.record.started_at <= end_at)
        and (status is None or item.record.response.status == status)
    ]


def time_range(
    records: Iterable[ParsedLogRecord],
    start_at: int | None = None,
    end_at: int | None = None,
) -> list[ParsedLogRecord]:
    """Return valid records in an inclusive integer timestamp range."""
    _validate_bounds(start_at, end_at)
    return _filter_time(_records(records), start_at, end_at)


def status_breakdown(
    records: Iterable[ParsedLogRecord],
    start_at: int | None = None,
    end_at: int | None = None,
) -> dict[int, int]:
    """Count response statuses, ordered by status number for stable output."""
    _validate_bounds(start_at, end_at)
    counts = Counter(
        item.record.response.status
        for item in _filter_time(records, start_at, end_at)
    )
    return {status: counts[status] for status in sorted(counts)}


def top_ips(
    records: Iterable[ParsedLogRecord],
    limit: int = 10,
    start_at: int | None = None,
    end_at: int | None = None,
    status: int | None = None,
) -> list[dict[str, Any]]:
    """Return IP counts filtered by status/time, with deterministic ordering."""
    _validate_limit(limit)
    _validate_bounds(start_at, end_at)
    _validate_status(status)
    counts = Counter(
        item.record.client_ip
        for item in _filter_time(records, start_at, end_at, status)
    )
    ranked = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
    return [
        {"client_ip": ip, "count": count}
        for ip, count in ranked[:limit]
    ]


def _route_name(item: ParsedLogRecord) -> str:
    """Use route.name; fall back to request.uri when route name is absent.

    An empty route name is treated as unavailable and falls back to URI.
    This is an aggregation-only convention and does not mutate C2 data.
    """
    if item.record.route is not None and item.record.route.name:
        return item.record.route.name
    return item.record.request.uri


def top_routes(
    records: Iterable[ParsedLogRecord],
    limit: int = 10,
    start_at: int | None = None,
    end_at: int | None = None,
    status: int | None = None,
) -> list[dict[str, Any]]:
    """Return route counts with route-name/URI fallback and stable tie-breaks."""
    _validate_limit(limit)
    _validate_bounds(start_at, end_at)
    _validate_status(status)
    counts = Counter(
        _route_name(item)
        for item in _filter_time(records, start_at, end_at, status)
    )
    ranked = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
    return [
        {"route": route, "count": count}
        for route, count in ranked[:limit]
    ]


def top_ip_route_pairs(
    records: Iterable[ParsedLogRecord],
    limit: int = 10,
    start_at: int | None = None,
    end_at: int | None = None,
    status: int | None = None,
) -> list[dict[str, Any]]:
    """Count (client_ip, route) pairs with count/IP/route stable ordering."""
    _validate_limit(limit)
    _validate_bounds(start_at, end_at)
    _validate_status(status)
    counts = Counter(
        (item.record.client_ip, _route_name(item))
        for item in _filter_time(records, start_at, end_at, status)
    )
    ranked = sorted(
        counts.items(),
        key=lambda pair: (-pair[1], pair[0][0], pair[0][1]),
    )
    return [
        {"client_ip": ip, "route": route, "count": count}
        for (ip, route), count in ranked[:limit]
    ]


def consumer_stats(
    records: Iterable[ParsedLogRecord],
    start_at: int | None = None,
    end_at: int | None = None,
    status: int | None = None,
) -> list[dict[str, Any]]:
    """Count consumers; missing, null and empty usernames map to ``anonymous``.

    The source model preserves the original state through
    ``KongConsumer.username_state`` and the original parsed object. This
    aggregation convention does not rewrite or normalize C2 fields.
    """
    _validate_bounds(start_at, end_at)
    _validate_status(status)
    counts = Counter()
    for item in _filter_time(records, start_at, end_at, status):
        consumer = (
            item.record.consumer.username
            if item.record.consumer is not None
            else None
        )
        counts[consumer or "anonymous"] += 1

    ranked = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
    return [
        {"consumer": consumer, "count": count}
        for consumer, count in ranked
    ]


def get_log_lines(
    records: Iterable[ParsedLogRecord],
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Return at most 20 records in physical line-number order.

    The returned data includes the derived ``line_id`` and a copy of the
    original parsed object for later citation verification.
    """
    _validate_limit(limit)
    effective_limit = min(limit, 20)
    ordered = sorted(_records(records), key=lambda item: item.line_number)
    return [
        {
            "line_id": item.line_id,
            "line_number": item.line_number,
            "record": item.original,
        }
        for item in ordered[:effective_limit]
    ]
