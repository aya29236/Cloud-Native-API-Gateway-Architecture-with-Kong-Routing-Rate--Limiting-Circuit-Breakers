"""Read-only HTTP endpoints over deterministic AI1 log tools."""

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, RootModel

from advisor.ai1.models import ParsedLogRecord
from advisor.ai1.reader import LogReaderResult, read_kong_log
from advisor.ai1.tools import (
    consumer_stats,
    get_log_lines,
    status_breakdown,
    time_range,
    top_ip_route_pairs,
    top_ips,
    top_routes,
)


DEFAULT_LOG_PATH = "/var/log/kong/access.json"


class StatusBreakdownResponse(RootModel[dict[int, int]]):
    pass


class CountItem(BaseModel):
    count: int


class TopIPItem(CountItem):
    client_ip: str


class TopIPsResponse(RootModel[list[TopIPItem]]):
    pass


class TopRouteItem(CountItem):
    route: str


class TopRoutesResponse(RootModel[list[TopRouteItem]]):
    pass


class TopPairItem(CountItem):
    client_ip: str
    route: str


class TopPairsResponse(RootModel[list[TopPairItem]]):
    pass


class ConsumerItem(CountItem):
    consumer: str


class ConsumersResponse(RootModel[list[ConsumerItem]]):
    pass


class TimeRangeResponse(RootModel[list[ParsedLogRecord]]):
    pass


class LogLineResponse(BaseModel):
    line_id: str
    line_number: int
    record: dict[str, Any]


class LogLinesResponse(RootModel[list[LogLineResponse]]):
    pass


class ReaderCountsResponse(BaseModel):
    valid: int
    blank: int
    malformed: int


router = APIRouter(prefix="/stats", tags=["stats"])


def get_log_result(request: Request) -> LogReaderResult:
    """Read the selected log file for this request, without caching across requests."""
    synthetic_path = getattr(request.app.state, "advisor_synthetic_log_path", None)
    if synthetic_path is not None:
        path = Path(synthetic_path)
    else:
        path = Path(os.getenv("KONG_LOG_PATH", DEFAULT_LOG_PATH))

    if not path.is_file():
        raise HTTPException(
            status_code=503,
            detail=f"Kong access log file is not available: {path}",
        )

    try:
        return read_kong_log(path)
    except OSError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Cannot read Kong access log file {path}: {exc}",
        ) from exc


def get_records(
    result: LogReaderResult = Depends(get_log_result),
) -> list[ParsedLogRecord]:
    """Dependency returning valid records from the current file read."""
    return result.records


def _call_tool(tool: Any, *args: Any, **kwargs: Any) -> Any:
    try:
        return tool(*args, **kwargs)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/status", response_model=StatusBreakdownResponse)
def read_status(
    start_at: int | None = Query(default=None),
    end_at: int | None = Query(default=None),
    records: list[ParsedLogRecord] = Depends(get_records),
) -> dict[int, int]:
    return _call_tool(status_breakdown, records, start_at, end_at)


@router.get("/top-ips", response_model=TopIPsResponse)
def read_top_ips(
    limit: int = Query(default=10),
    start_at: int | None = Query(default=None),
    end_at: int | None = Query(default=None),
    records: list[ParsedLogRecord] = Depends(get_records),
) -> list[dict[str, Any]]:
    return _call_tool(top_ips, records, limit, start_at, end_at)


@router.get("/top-routes", response_model=TopRoutesResponse)
def read_top_routes(
    limit: int = Query(default=10),
    start_at: int | None = Query(default=None),
    end_at: int | None = Query(default=None),
    records: list[ParsedLogRecord] = Depends(get_records),
) -> list[dict[str, Any]]:
    return _call_tool(top_routes, records, limit, start_at, end_at)


@router.get("/top-pairs", response_model=TopPairsResponse)
def read_top_pairs(
    limit: int = Query(default=10),
    start_at: int | None = Query(default=None),
    end_at: int | None = Query(default=None),
    records: list[ParsedLogRecord] = Depends(get_records),
) -> list[dict[str, Any]]:
    return _call_tool(top_ip_route_pairs, records, limit, start_at, end_at)


@router.get("/consumers", response_model=ConsumersResponse)
def read_consumers(
    start_at: int | None = Query(default=None),
    end_at: int | None = Query(default=None),
    records: list[ParsedLogRecord] = Depends(get_records),
) -> list[dict[str, Any]]:
    return _call_tool(consumer_stats, records, start_at, end_at)


@router.get("/time-range", response_model=TimeRangeResponse)
def read_time_range(
    start_at: int | None = Query(default=None),
    end_at: int | None = Query(default=None),
    records: list[ParsedLogRecord] = Depends(get_records),
) -> list[ParsedLogRecord]:
    return _call_tool(time_range, records, start_at, end_at)


@router.get("/lines", response_model=LogLinesResponse)
def read_lines(
    limit: int = Query(default=20),
    records: list[ParsedLogRecord] = Depends(get_records),
) -> list[dict[str, Any]]:
    lines = _call_tool(get_log_lines, records, min(limit, 20))
    return lines[:20]


@router.get("/reader-counts", response_model=ReaderCountsResponse)
def read_reader_counts(
    result: LogReaderResult = Depends(get_log_result),
) -> ReaderCountsResponse:
    return ReaderCountsResponse(
        valid=result.valid_count,
        blank=result.blank_count,
        malformed=result.malformed_count,
    )
