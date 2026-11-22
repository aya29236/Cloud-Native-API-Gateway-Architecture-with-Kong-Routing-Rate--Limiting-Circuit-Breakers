"""Deterministic Kong access-log reading and analysis tools."""

from .models import (
    KongConsumer,
    KongLogRecord,
    KongRequest,
    KongResponse,
    KongRoute,
    KongService,
    ParsedLogRecord,
)
from .reader import (
    LogReaderError,
    LogReaderResult,
    read_kong_log,
    read_kong_log_text,
)
from .tools import (
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
from .generator import generate_synthetic_logs

__all__ = [
    "KongConsumer",
    "KongLogRecord",
    "KongRequest",
    "KongResponse",
    "KongRoute",
    "KongService",
    "LogReaderError",
    "LogReaderResult",
    "ParsedLogRecord",
    "read_kong_log",
    "read_kong_log_text",
    "time_range",
    "status_breakdown",
    "top_ips",
    "top_routes",
    "top_ip_route_pairs",
    "consumer_stats",
    "get_log_lines",
    "generate_synthetic_logs",
    "TimeRangeArgs",
    "StatusBreakdownArgs",
    "TopIPsArgs",
    "TopRoutesArgs",
    "TopIPRoutePairsArgs",
    "ConsumerStatsArgs",
    "GetLogLinesArgs",
]
