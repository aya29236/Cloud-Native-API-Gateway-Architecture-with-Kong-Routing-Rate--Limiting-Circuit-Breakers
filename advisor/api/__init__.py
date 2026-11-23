"""Reusable FastAPI routers for the advisor service."""

from .analyze import router as analyze_router
from .stats import router as stats_router

__all__ = ["analyze_router", "stats_router"]
