"""Read proposed C2 Kong access logs from a single object or JSONL text."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from pydantic import ValidationError

from .models import KongLogRecord, ParsedLogRecord


@dataclass(frozen=True)
class LogReaderError:
    """A blank or malformed physical input line."""

    line_number: int
    line_id: str
    error: str
    kind: str


@dataclass(frozen=True)
class LogReaderResult:
    """Valid records, plus separate malformed-line diagnostics."""

    records: list[ParsedLogRecord]
    errors: list[LogReaderError]

    @property
    def valid_count(self) -> int:
        return len(self.records)

    @property
    def blank_count(self) -> int:
        return sum(error.kind == "blank" for error in self.errors)

    @property
    def malformed_count(self) -> int:
        return sum(error.kind == "malformed" for error in self.errors)


def _parse_record(
    value: Any,
    line_number: int,
) -> ParsedLogRecord | LogReaderError:
    line_id = f"L{line_number}"
    if not isinstance(value, dict):
        return LogReaderError(
            line_number=line_number,
            line_id=line_id,
            error="record must be a JSON object",
            kind="malformed",
        )

    try:
        record = KongLogRecord.model_validate(value)
    except ValidationError as exc:
        details = "; ".join(
            f"{'.'.join(str(part) for part in issue['loc'])}: {issue['msg']}"
            for issue in exc.errors()
        )
        return LogReaderError(
            line_number=line_number,
            line_id=line_id,
            error=details,
            kind="malformed",
        )

    return ParsedLogRecord(
        line_id=line_id,
        line_number=line_number,
        record=record,
        original=value,
    )


def _objects_from_text(text: str) -> Iterable[tuple[int, Any | None, str | None, str | None]]:
    """Yield complete JSON, JSONL records, or a classified input error."""
    if not text or not text.strip():
        return

    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        value = None
    else:
        first_character = len(text) - len(text.lstrip())
        line_number = text.count("\n", 0, first_character) + 1
        if isinstance(value, dict):
            yield line_number, value, None, None
        else:
            yield line_number, value, "unsupported JSON top-level value", "malformed"
        return

    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            yield line_number, None, "blank line", "blank"
            continue
        try:
            yield line_number, json.loads(line), None, None
        except json.JSONDecodeError as exc:
            yield line_number, None, f"invalid JSON: {exc.msg}", "malformed"


def read_kong_log(source: str | Path) -> LogReaderResult:
    """Read a UTF-8 Kong log file.

    A complete JSON object is read first, so the repository fixture is
    supported. Otherwise, each physical line is parsed independently as JSON.
    Blank lines and malformed values never prevent later lines from being read.
    """
    path = Path(source)
    text = path.read_text(encoding="utf-8")
    records: list[ParsedLogRecord] = []
    errors: list[LogReaderError] = []

    for line_number, value, pre_parse_error, kind in _objects_from_text(text):
        line_id = f"L{line_number}"
        if pre_parse_error is not None:
            errors.append(
                LogReaderError(
                    line_number=line_number,
                    line_id=line_id,
                    error=pre_parse_error,
                    kind=kind or "malformed",
                )
            )
            continue

        parsed = _parse_record(value, line_number)
        if isinstance(parsed, LogReaderError):
            errors.append(parsed)
        else:
            records.append(parsed)

    return LogReaderResult(records=records, errors=errors)


def read_kong_log_text(text: str) -> LogReaderResult:
    """Read text directly; useful for tests and non-file callers."""
    records: list[ParsedLogRecord] = []
    errors: list[LogReaderError] = []

    for line_number, value, pre_parse_error, kind in _objects_from_text(text):
        line_id = f"L{line_number}"
        if pre_parse_error is not None:
            errors.append(
                LogReaderError(
                    line_number=line_number,
                    line_id=line_id,
                    error=pre_parse_error,
                    kind=kind or "malformed",
                )
            )
            continue

        parsed = _parse_record(value, line_number)
        if isinstance(parsed, LogReaderError):
            errors.append(parsed)
        else:
            records.append(parsed)

    return LogReaderResult(records=records, errors=errors)
