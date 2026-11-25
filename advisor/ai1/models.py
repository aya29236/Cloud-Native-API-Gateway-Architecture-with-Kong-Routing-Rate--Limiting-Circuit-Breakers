"""Pydantic models for the proposed C2 Kong access-log record."""

from typing import Any

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    """Reject implicit primitive coercion and preserve extra C2 fields."""

    model_config = ConfigDict(strict=True, extra="allow")


class KongRequest(StrictModel):
    method: str
    uri: str


class KongResponse(StrictModel):
    status: int


class KongConsumer(StrictModel):
    username: str | None = None

    def username_state(self) -> str:
        """Distinguish missing, null, empty, and populated usernames."""
        if "username" not in self.model_fields_set:
            return "missing"
        if self.username is None:
            return "null"
        if self.username == "":
            return "empty"
        return "present"


class KongRoute(StrictModel):
    name: str | None = None

    def name_state(self) -> str:
        """Distinguish missing, null, empty, and populated route names."""
        if "name" not in self.model_fields_set:
            return "missing"
        if self.name is None:
            return "null"
        if self.name == "":
            return "empty"
        return "present"


class KongService(StrictModel):
    name: str | None = None


class KongLogRecord(StrictModel):
    """C2-shaped Kong access-log record.

    ``started_at`` is intentionally kept as the source integer. Its unit and
    timezone remain provisional until Aya verifies live Kong 3.9.1 output.
    """

    client_ip: str
    request: KongRequest
    response: KongResponse
    latencies: dict[str, Any]
    consumer: KongConsumer | None = None
    route: KongRoute | None = None
    service: KongService | None = None
    started_at: int


class ParsedLogRecord(StrictModel):
    """One valid log record plus its physical source location."""

    line_id: str
    line_number: int
    record: KongLogRecord
    original: dict[str, Any]
