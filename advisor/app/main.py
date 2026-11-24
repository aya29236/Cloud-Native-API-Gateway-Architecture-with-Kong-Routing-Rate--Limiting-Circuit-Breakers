"""FastAPI AI Advisor shell (V3.1).

The shell owns the HTTP contract, the Pydantic models, the health endpoint,
the gateway headers and the read-only log mount (added in V3.2). Student C
replaces `analyze()` with the real verified-tool analyzer later; until then it
returns the safe C1 answer "No verified data" with verified=false.
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .middleware import GatewayHeadersMiddleware
from .models import AnalyzeRequest, AnalyzeResponse, HealthResponse

app = FastAPI(title="AI Advisor", version="0.1.0")
app.add_middleware(GatewayHeadersMiddleware)

# Placeholder values until Student C wires the analyzer to the log store.
KNOWN_STATS: dict[str, int] = {
    "requests_total": 0,
    "errors_total": 0,
    "rate_limited_total": 0,
}


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    """C1 declares 400 for a bad request body; FastAPI defaults to 422."""
    return JSONResponse(status_code=400, content=jsonable_encoder({"detail": exc.errors()}))


@app.get("/health", response_model=HealthResponse)
def health():
    return {"status": "healthy"}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(payload: AnalyzeRequest):
    """Stub: never invent an answer from unverified data."""
    return AnalyzeResponse(
        summary="No verified data",
        stats={},
        citations=[],
        tool_trace=[],
        verified=False,
    )


@app.get("/stats")
def stats():
    return dict(KNOWN_STATS)


@app.get("/stats/{stat_name}")
def named_stat(stat_name: str):
    if stat_name not in KNOWN_STATS:
        raise HTTPException(status_code=404, detail="Unknown statistic")
    return {stat_name: KNOWN_STATS[stat_name]}
