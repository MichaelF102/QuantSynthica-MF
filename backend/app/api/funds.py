from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import (
    AMC,
    DataQualityIssue,
    ExternalId,
    FundCategory,
    FundSnapshot,
    IngestionRun,
    Scheme,
    SchemeMetric,
)
from app.schemas.funds import (
    DataQualitySummary,
    FundDetail,
    FundList,
    FundSummary,
    SiblingScheme,
)

router = APIRouter(prefix="/api/v1", tags=["funds"])

SORTABLE = {
    "name": Scheme.name,
    "price": FundSnapshot.price,
    "change_pct": FundSnapshot.change_pct,
    "ytd_return": FundSnapshot.ytd_return,
    "return_3m": FundSnapshot.return_3m,
    "return_1y": FundSnapshot.return_1y,
    "return_3y": FundSnapshot.return_3y,
    "return_5y": FundSnapshot.return_5y,
    "net_assets": FundSnapshot.net_assets,
}


def latest_run_id(session: Session) -> int | None:
    return session.scalar(
        select(func.max(IngestionRun.id)).where(IngestionRun.status == "succeeded", IngestionRun.source == "yahoo_csv")
    )


def _summary_columns():
    return (
        Scheme.id, Scheme.name, AMC.name.label("amc"), FundCategory.name.label("category"),
        Scheme.asset_tier, Scheme.plan_type, Scheme.option_type, Scheme.is_insurer_fund,
        Scheme.is_discontinued, FundSnapshot.quarantined, FundSnapshot.price, FundSnapshot.change_pct,
        FundSnapshot.ytd_return, FundSnapshot.return_3m, FundSnapshot.return_1y,
        FundSnapshot.return_3y, FundSnapshot.return_5y, FundSnapshot.net_assets,
    )


@router.get("/funds", response_model=FundList)
def list_funds(
    session: Annotated[Session, Depends(get_session)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    sort: str = "name",
    order: Literal["asc", "desc"] = "asc",
    q: str | None = Query(None, max_length=100, description="substring of fund or AMC name"),
    asset_tier: str | None = None,
    category: str | None = None,
    amc: str | None = None,
    plan_type: str | None = None,
    option_type: str | None = None,
    include_quarantined: bool = False,
    include_discontinued: bool = True,
) -> FundList:
    run_id = latest_run_id(session)
    if run_id is None:
        return FundList(items=[], total=0, page=page, page_size=page_size, ingestion_run_id=None)
    if sort not in SORTABLE:
        raise HTTPException(422, f"sort must be one of {sorted(SORTABLE)}")

    base = (
        select(*_summary_columns())
        .join(FundSnapshot, FundSnapshot.scheme_id == Scheme.id)
        .join(AMC, AMC.id == Scheme.amc_id)
        .join(FundCategory, FundCategory.id == Scheme.category_id)
        .where(FundSnapshot.ingestion_run_id == run_id)
    )
    if q:
        like = f"%{q.lower()}%"
        base = base.where(func.lower(Scheme.name).like(like) | func.lower(AMC.name).like(like))
    if asset_tier:
        base = base.where(Scheme.asset_tier == asset_tier)
    if category:
        base = base.where(FundCategory.name == category)
    if amc:
        base = base.where(AMC.name == amc)
    if plan_type:
        base = base.where(Scheme.plan_type == plan_type)
    if option_type:
        base = base.where(Scheme.option_type == option_type)
    if not include_quarantined:
        base = base.where(FundSnapshot.quarantined.is_(False))
    if not include_discontinued:
        base = base.where(Scheme.is_discontinued.is_(False))

    total = session.scalar(select(func.count()).select_from(base.subquery())) or 0
    col = SORTABLE[sort]
    ordering = col.asc().nulls_last() if order == "asc" else col.desc().nulls_last()
    rows = session.execute(
        base.order_by(ordering, Scheme.id).offset((page - 1) * page_size).limit(page_size)
    ).all()

    symbols = dict(
        session.execute(
            select(ExternalId.scheme_id, ExternalId.value).where(
                ExternalId.id_type == "yahoo_symbol", ExternalId.scheme_id.in_([r.id for r in rows])
            )
        ).all()
    )
    items = [FundSummary(symbol=symbols.get(r.id), **r._asdict()) for r in rows]
    return FundList(items=items, total=total, page=page, page_size=page_size, ingestion_run_id=run_id)


@router.get("/funds/{fund_id}", response_model=FundDetail)
def get_fund(fund_id: int, session: Annotated[Session, Depends(get_session)]) -> FundDetail:
    run_id = latest_run_id(session)
    if run_id is None:
        raise HTTPException(404, "no data ingested")
    row = session.execute(
        select(*_summary_columns(), Scheme.family_id, Scheme.idcw_mode, Scheme.idcw_freq, Scheme.n_share_classes,
               FundSnapshot.avg_50d, FundSnapshot.avg_200d, FundSnapshot.low_52w, FundSnapshot.high_52w,
               FundSnapshot.initial_investment, FundSnapshot.market_cap_value, FundSnapshot.price_change_52w_pct,
               FundSnapshot.features)
        .join(FundSnapshot, FundSnapshot.scheme_id == Scheme.id)
        .join(AMC, AMC.id == Scheme.amc_id)
        .join(FundCategory, FundCategory.id == Scheme.category_id)
        .where(Scheme.id == fund_id, FundSnapshot.ingestion_run_id == run_id)
    ).first()
    if row is None:
        raise HTTPException(404, "fund not found")
    data = row._asdict()

    ext = {e.id_type: e.value for e in session.scalars(select(ExternalId).where(ExternalId.scheme_id == fund_id))}
    scheme = session.get(Scheme, fund_id)
    base_fund = scheme.family.base_fund if scheme and scheme.family else None
    siblings = []
    if data["family_id"] is not None:
        siblings = [
            SiblingScheme(id=s.id, name=s.name, plan_type=s.plan_type, option_type=s.option_type,
                          idcw_mode=s.idcw_mode, idcw_freq=s.idcw_freq)
            for s in session.scalars(
                select(Scheme).where(Scheme.family_id == data["family_id"], Scheme.id != fund_id).order_by(Scheme.name)
            )
        ]
    issues = [
        {"rule": i.rule, "severity": i.severity, "detail": i.detail}
        for i in session.scalars(
            select(DataQualityIssue).where(DataQualityIssue.scheme_id == fund_id, DataQualityIssue.ingestion_run_id == run_id)
        )
    ]
    run = session.get(IngestionRun, run_id)
    m = session.get(SchemeMetric, fund_id)
    nav_metrics = None if m is None else {
        "as_of": m.as_of.date().isoformat(), "ret_1y": m.ret_1y, "ret_3y": m.ret_3y, "ret_5y": m.ret_5y,
        "methodology_version": m.methodology_version,
    }
    return FundDetail(nav_metrics=nav_metrics, 
        symbol=ext.get("yahoo_symbol"), base_fund=base_fund, external_ids=ext, siblings=siblings,
        quality_issues=issues, ingestion_run_id=run_id, data_asof=run.source_asof if run else None, **data,
    )


@router.get("/data-quality", response_model=DataQualitySummary)
def data_quality(session: Annotated[Session, Depends(get_session)]) -> DataQualitySummary:
    run_id = latest_run_id(session)
    note = "Snapshot date of the source CSV is unknown; values are a single cross-section, not history."
    if run_id is None:
        return DataQualitySummary(ingestion_run_id=None, status=None, file_name=None, file_sha256=None, rows_read=None,
                                  rows_quarantined=None, summary=None, issues_by_rule={}, note=note)
    run = session.get(IngestionRun, run_id)
    by_rule: dict[str, dict[str, int]] = {}
    for rule, sev, n in session.execute(
        select(DataQualityIssue.rule, DataQualityIssue.severity, func.count())
        .where(DataQualityIssue.ingestion_run_id == run_id)
        .group_by(DataQualityIssue.rule, DataQualityIssue.severity)
    ):
        by_rule.setdefault(rule, {})[sev] = n
    return DataQualitySummary(
        ingestion_run_id=run_id, status=run.status, file_name=run.file_name, file_sha256=run.file_sha256,
        rows_read=run.rows_read, rows_quarantined=run.rows_quarantined, summary=run.summary,
        issues_by_rule=by_rule, note=note,
    )
