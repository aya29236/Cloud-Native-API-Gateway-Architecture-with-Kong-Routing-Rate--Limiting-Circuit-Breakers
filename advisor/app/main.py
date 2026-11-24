"""FastAPI AI Advisor with the C1 contract and a verified tool loop (V3.3).

The shell owns the HTTP contract, Pydantic models, health endpoint and gateway
headers. Layer 5 replaces the V3.1 stub with the real analyzer, which reads the
read-only Kong log mount and never answers without verified tool support.
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .analyzer import answer_question, current_stats
from .middleware import GatewayHeadersMiddleware
from .models import AnalyzeRequest, AnalyzeResponse, HealthResponse

app = FastAPI(title="AI Advisor", version="0.2.0")
app.add_middleware(GatewayHeadersMiddleware)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    """C1 declares 400 for a bad request body; FastAPI defaults to 422."""
    return JSONResponse(status_code=400, content=jsonable_encoder({"detail": exc.errors()}))


@app.get("/health", response_model=HealthResponse)
def health():
    return {"status": "healthy"}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(payload: AnalyzeRequest):
    """Answer only from verified tool results; otherwise use the C1 fallback."""
    return answer_question(payload.question)


@app.get("/stats")
def stats():
    return current_stats()


@app.get("/stats/{stat_name}")
def named_stat(stat_name: str):
    values = current_stats()
    if stat_name not in values:
        raise HTTPException(status_code=404, detail="Unknown statistic")
    return {stat_name: values[stat_name]}
