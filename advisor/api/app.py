"""Standalone local FastAPI application for advisor routers."""

import os
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Request
from pydantic import BaseModel

from advisor.ai1.generator import generate_synthetic_logs
from advisor.api.analyze import router as analyze_router
from advisor.api.stats import router as stats_router


class HealthResponse(BaseModel):
    status: Literal["healthy"] = "healthy"
    data_source: Literal["synthetic", "kong-log"]


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        configured_path = os.getenv("KONG_LOG_PATH")
        if configured_path and Path(configured_path).is_file():
            application.state.advisor_data_source = "kong-log"
            application.state.advisor_synthetic_log_path = None
            application.state.advisor_generated_log_path = None
        else:
            text, _raw_records, _expected = generate_synthetic_logs(seed=2026)
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                suffix=".jsonl",
                prefix="advisor-synthetic-",
                delete=False,
            ) as log_file:
                log_file.write(text)
                generated_path = Path(log_file.name)
            application.state.advisor_data_source = "synthetic"
            application.state.advisor_synthetic_log_path = generated_path
            application.state.advisor_generated_log_path = generated_path

        try:
            yield
        finally:
            generated_path = getattr(
                application.state,
                "advisor_generated_log_path",
                None,
            )
            if generated_path is not None:
                Path(generated_path).unlink(missing_ok=True)

    application = FastAPI(
        title="Student C Advisor API",
        description="Read-only deterministic log statistics and verified analysis.",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.include_router(stats_router)
    application.include_router(analyze_router)

    @application.get("/health", response_model=HealthResponse)
    def health(request: Request) -> HealthResponse:
        data_source = getattr(
            request.app.state,
            "advisor_data_source",
            "kong-log",
        )
        return HealthResponse(data_source=data_source)

    return application


app = create_app()
