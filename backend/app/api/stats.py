from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from quant_engine import backtest as bt
from quant_engine import scoring
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import get_session
from app.models import AMC, FundCategory, FundScore, NavCoverage, Scheme, SchemeMapping
from app.services.analytics import ACCEPTED, nav_store

router = APIRouter(prefix="/api/v1", tags=["stats"])
_cache: dict[str, Any] = {"at": 0.0, "value": None}


@router.get("/platform-stats")
def platform_stats(session: Annotated[Session, Depends(get_session)]) -> dict[str, Any]:
    """Counts shown on the landing page. Every figure is computed from loaded data; a missing piece is null, never a guess.
    Cached for 10 minutes because the NAV row count reads Parquet metadata."""
    now = datetime.now(UTC).timestamp()
    if _cache["value"] is not None and now - _cache["at"] < 600:
        return _cache["value"]
    def count(q) -> int:
        return int(session.scalar(q) or 0)

    funds = count(select(func.count()).select_from(Scheme).where(Scheme.is_insurer_fund.is_(False)))
    first, last = session.execute(select(func.min(NavCoverage.first_date), func.max(NavCoverage.last_date))).one()
    try:
        rows = nav_store().row_count() or None
    except Exception:
        rows = None
    value = {
        "funds": funds or None,
        "fund_houses": count(select(func.count()).select_from(AMC).where(AMC.is_insurer.is_(False))) or None,
        "categories": count(select(func.count()).select_from(FundCategory)) or None,
        "funds_with_nav_history": count(select(func.count(func.distinct(SchemeMapping.scheme_id))).where(SchemeMapping.status.in_(ACCEPTED))) or None,
        "funds_scored": count(select(func.count()).select_from(FundScore).where(FundScore.composite.is_not(None))) or None,
        "nav_observations": rows,
        "history_from": first.date().isoformat() if first else None,
        "history_to": last.date().isoformat() if last else None,
        "strategies_tested": len(bt.STRATEGIES),
        "score_version": scoring.SCORE_VERSION,
        "data_dir_configured": bool(get_settings().data_dir),
    }
    _cache.update(at=now, value=value)
    return value
