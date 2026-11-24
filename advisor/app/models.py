"""Pydantic models for the C1 Advisor contract (V3.1).

Pydantic is the FastAPI equivalent of DRF serializers: it validates incoming
JSON and shapes outgoing JSON. `extra="forbid"` enforces C1's
`additionalProperties: false`.
"""

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

Citation = Annotated[str, Field(pattern=r"^\[L[0-9]+\]$")]


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1)


class AnalyzeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    stats: dict[str, Any]
    citations: list[Citation]
    tool_trace: list[dict[str, Any]]
    verified: bool


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
