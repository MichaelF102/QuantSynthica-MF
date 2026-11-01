from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.funds import latest_run_id
from app.db import get_session
from app.models import AMC, FundCategory, FundSnapshot, Scheme
from app.services import overview as ov

router = APIRouter(prefix="/api/v1", tags=["overview"])


@router.get("/overview")
def get_overview(
    session: Annotated[Session, Depends(get_session)],
    include_insurer: bool = False,
    horizon: str = Query("1y", description="horizon for the top-performers table"),
) -> dict[str, Any]:
    run_id = latest_run_id(session)
    if run_id is None:
        raise HTTPException(404, "no data ingested")
    try:
        return ov.overview(session, run_id, include_insurer=include_insurer, top_horizon=horizon)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/filters/options")
def filter_options(session: Annotated[Session, Depends(get_session)]) -> dict[str, Any]:
    """Distinct values with counts, for filter dropdowns."""
    run_id = latest_run_id(session)
    if run_id is None:
        return {"amcs": [], "categories": [], "asset_tiers": [], "plan_types": [], "option_types": []}

    def counts(col, *joins):
        q = select(col, func.count()).select_from(Scheme).join(FundSnapshot, FundSnapshot.scheme_id == Scheme.id)
        for target, on in joins:
            q = q.join(target, on)
        q = q.where(FundSnapshot.ingestion_run_id == run_id).group_by(col).order_by(col)
        return [{"value": v, "count": n} for v, n in session.execute(q) if v is not None]

    return {
        "amcs": counts(AMC.name, (AMC, AMC.id == Scheme.amc_id)),
        "categories": counts(FundCategory.name, (FundCategory, FundCategory.id == Scheme.category_id)),
        "asset_tiers": counts(Scheme.asset_tier),
        "plan_types": counts(Scheme.plan_type),
        "option_types": counts(Scheme.option_type),
    }
