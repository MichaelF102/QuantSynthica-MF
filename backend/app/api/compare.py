from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.funds import latest_run_id
from app.db import get_session
from app.models import AMC, ExternalId, FundCategory, FundSnapshot, Scheme
from app.schemas.funds import FundSummary

router = APIRouter(prefix="/api/v1", tags=["compare"])
MAX_FUNDS = 5

PCT_KEYS = {
    "cat_pct_ytd": "ytd_return_cat_pct", "cat_pct_3m": "3mo_return_cat_pct", "cat_pct_1y": "1year_return_cat_pct",
    "cat_pct_3y": "3year_return_cat_pct", "cat_pct_5y": "5year_return_cat_pct",
}
RAW_KEYS = {"range_position": 100.0, "price_vs_50d": 100.0, "price_vs_200d": 100.0, "trend_50_200": 100.0,
            "pct_from_52w_high": 100.0}


class CompareFund(FundSummary):
    avg_50d: float | None
    avg_200d: float | None
    low_52w: float | None
    high_52w: float | None
    initial_investment: float | None
    metrics: dict[str, float | None]


class CompareResult(BaseModel):
    funds: list[CompareFund]
    warnings: list[str]
    ingestion_run_id: int


@router.get("/compare", response_model=CompareResult)
def compare(
    session: Annotated[Session, Depends(get_session)],
    ids: Annotated[str, Query(description="comma separated scheme ids, 2 to 5")],
) -> CompareResult:
    try:
        wanted = list(dict.fromkeys(int(x) for x in ids.split(",") if x.strip()))
    except ValueError as exc:
        raise HTTPException(422, "ids must be integers") from exc
    if not 1 <= len(wanted) <= MAX_FUNDS:
        raise HTTPException(422, f"choose between 1 and {MAX_FUNDS} funds")
    run_id = latest_run_id(session)
    if run_id is None:
        raise HTTPException(404, "no data ingested")

    rows = session.execute(
        select(Scheme.id, Scheme.name, AMC.name.label("amc"), FundCategory.name.label("category"), Scheme.asset_tier,
               Scheme.plan_type, Scheme.option_type, Scheme.is_insurer_fund, Scheme.is_discontinued,
               FundSnapshot.quarantined, FundSnapshot.price, FundSnapshot.change_pct, FundSnapshot.ytd_return,
               FundSnapshot.return_3m, FundSnapshot.return_1y, FundSnapshot.return_3y, FundSnapshot.return_5y,
               FundSnapshot.net_assets, FundSnapshot.avg_50d, FundSnapshot.avg_200d, FundSnapshot.low_52w,
               FundSnapshot.high_52w, FundSnapshot.initial_investment, FundSnapshot.features)
        .select_from(Scheme).join(FundSnapshot, FundSnapshot.scheme_id == Scheme.id)
        .join(AMC, AMC.id == Scheme.amc_id).join(FundCategory, FundCategory.id == Scheme.category_id)
        .where(Scheme.id.in_(wanted), FundSnapshot.ingestion_run_id == run_id)
    ).all()
    by_id = {r.id: r for r in rows}
    missing = [i for i in wanted if i not in by_id]
    if missing:
        raise HTTPException(404, f"funds not found: {missing}")
    symbols = dict(
        session.execute(
            select(ExternalId.scheme_id, ExternalId.value).where(
                ExternalId.id_type == "yahoo_symbol", ExternalId.scheme_id.in_(wanted)
            )
        ).all()
    )

    funds: list[CompareFund] = []
    for i in wanted:
        r = by_id[i]
        d = r._asdict()
        feats: dict[str, Any] = d.pop("features")
        metrics: dict[str, float | None] = {}
        for pub, key in PCT_KEYS.items():
            v = feats.get(key)
            metrics[pub] = None if v is None else v * 100
        for key, scale in RAW_KEYS.items():
            v = feats.get(key)
            metrics[key] = None if v is None else v * scale
        funds.append(CompareFund(symbol=symbols.get(i), metrics=metrics, **d))

    warnings: list[str] = []
    if len({f.category for f in funds}) > 1:
        warnings.append("Funds are in different categories; category percentiles are not comparable across categories.")
    if len({f.asset_tier for f in funds}) > 1:
        warnings.append("Funds span different asset tiers (e.g. equity vs debt); raw returns are not like-for-like.")
    if len({(f.plan_type, f.option_type) for f in funds}) > 1:
        warnings.append("Share classes differ in plan/option (Direct vs Regular, Growth vs IDCW); returns are not like-for-like.")
    if any(f.plan_type == "Unspecified" or f.option_type == "Unspecified" for f in funds):
        warnings.append("Some funds have an unspecified plan or option in the source data.")
    return CompareResult(funds=funds, warnings=warnings, ingestion_run_id=run_id)
