import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    account,
    admin,
    analytics,
    assistant,
    compare,
    coverage,
    funds,
    health,
    overview,
    portfolio,
    quant,
    reports,
    screener,
    stats,
)
from app.core.config import get_settings
from app.core.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level)
log = logging.getLogger("qsmf")

app = FastAPI(title="QuantSynthica Mutual Funds API", version="0.1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=settings.cors_origins, allow_origin_regex=settings.cors_origin_regex, allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["*"],
)
app.include_router(health.router)
app.include_router(funds.router)
app.include_router(overview.router)
app.include_router(screener.router)
app.include_router(compare.router)
app.include_router(coverage.router)
app.include_router(analytics.router)
app.include_router(quant.router)
app.include_router(portfolio.router)
app.include_router(reports.router)
app.include_router(account.router)
app.include_router(assistant.router)
app.include_router(admin.router)
app.include_router(stats.router)
