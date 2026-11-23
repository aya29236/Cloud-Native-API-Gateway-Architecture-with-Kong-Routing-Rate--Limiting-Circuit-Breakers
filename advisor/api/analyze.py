"""LLM-backed C1 analysis endpoint, verified by AI3."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from advisor.ai1.models import ParsedLogRecord
from advisor.ai2.agent import AnalyzeResponse
from advisor.ai2.llm import LLMClient, OllamaClient
from advisor.ai3.pipeline import analyze_verified

from .stats import get_records


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1)


router = APIRouter(tags=["analyze"])


def get_llm_client() -> LLMClient:
    try:
        return OllamaClient()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _llm_service_error(response: AnalyzeResponse) -> str | None:
    for trace in response.tool_trace:
        error: Any = trace.get("error")
        if not isinstance(error, str) or not error.startswith("LLM error:"):
            continue
        detail = error.removeprefix("LLM error:").strip()
        if "http error 404" in detail.lower() or "model not found" in detail.lower():
            return (
                f"{detail}. The configured Ollama model may not be pulled; "
                "verify ADVISOR_MODEL and the model available to Ollama."
            )
        return detail
    return None


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(
    request: AnalyzeRequest,
    records: list[ParsedLogRecord] = Depends(get_records),
    client: LLMClient = Depends(get_llm_client),
) -> AnalyzeResponse:
    response = analyze_verified(request.question, records, client)
    service_error = _llm_service_error(response)
    if service_error is not None:
        raise HTTPException(status_code=503, detail=service_error)
    return response
