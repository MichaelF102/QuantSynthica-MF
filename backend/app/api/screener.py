import csv
import io
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import Float, cast, func, select
from sqlalchemy.orm import Session

from app.api.funds import latest_run_id
from app.db import get_session
from app.models import (
    AMC,
    ExternalId,
    FundCategory,
    FundScore,
    FundSnapshot,
    Scheme,
    SchemeMetric,
)
from app.schemas.funds import FundSummary
from app.services import screener as sc

router = APIRouter(prefix="/api/v1/screener", tags=["screener"])
EXPORT_CAP = 10000


class ScreenRequest(BaseModel):
    filter: sc.Group = Field(default_factory=sc.Group)
    sort: str = "name"
    order: Literal["asc", "desc"] = "asc"
    page: int = Field(1, ge=1)
    page_size: int = Field(50, ge=1, le=200)
    include_quarantined: bool = False


class ScreenRow(FundSummary):
    cat_pct_1y: float | None
    cat_pct_3y: float | None
    cat_pct_5y: float | None
    price_vs_200d: float | None
    sharpe_3y: float | None = None
    vol_3y: float | None = None
    max_dd_3y: float | None = None
    nav_ret_3y: float | None = None
    quant_score: float | None = None


class ScreenResult(BaseModel):
    items: list[ScreenRow]
    total: int
    page: int
    page_size: int
    ingestion_run_id: int | None


def _feat(key: str, scale: float):
    return (cast(FundSnapshot.features.op("->>")(key), Float) * scale).label


def _query(req: ScreenRequest, run_id: int):
    try:
        sc.validate_tree(req.filter)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    order_col = sc.sort_expr(req.sort)
    if order_col is None:
        raise HTTPException(422, f"cannot sort by '{req.sort}'")
    cols = (
        Scheme.id, Scheme.name, AMC.name.label("amc"), FundCategory.name.label("category"),
        Scheme.asset_tier, Scheme.plan_type, Scheme.option_type, Scheme.is_insurer_fund,
        Scheme.is_discontinued, FundSnapshot.quarantined, FundSnapshot.price, FundSnapshot.change_pct,
        FundSnapshot.ytd_return, FundSnapshot.return_3m, FundSnapshot.return_1y, FundSnapshot.return_3y,
        FundSnapshot.return_5y, FundSnapshot.net_assets,
        _feat("1year_return_cat_pct", 100)("cat_pct_1y"),
        _feat("3year_return_cat_pct", 100)("cat_pct_3y"),
        _feat("5year_return_cat_pct", 100)("cat_pct_5y"),
        _feat("price_vs_200d", 100)("price_vs_200d"),
        SchemeMetric.sharpe_3y, SchemeMetric.vol_3y, SchemeMetric.max_dd_3y, SchemeMetric.ret_3y.label("nav_ret_3y"), FundScore.composite.label("quant_score"),
    )
    q = (
        select(*cols)
        .join(FundSnapshot, FundSnapshot.scheme_id == Scheme.id)
        .join(AMC, AMC.id == Scheme.amc_id)
        .join(FundCategory, FundCategory.id == Scheme.category_id)
        .outerjoin(SchemeMetric, SchemeMetric.scheme_id == Scheme.id)
        .outerjoin(FundScore, FundScore.scheme_id == Scheme.id)
        .where(FundSnapshot.ingestion_run_id == run_id)
        .where(sc.build_where(req.filter))
    )
    if not req.include_quarantined:
        q = q.where(FundSnapshot.quarantined.is_(False))
    ordering = order_col.asc().nulls_last() if req.order == "asc" else order_col.desc().nulls_last()
    return q, ordering


def _safe(v):
    """Neutralise spreadsheet formula injection in text cells; leave numbers untouched."""
    if v is None:
        return ""
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + v
    return v


@router.get("/fields")
def fields() -> list[dict]:
    return sc.field_catalog()


@router.post("", response_model=ScreenResult)
def screen(req: ScreenRequest, session: Annotated[Session, Depends(get_session)]) -> ScreenResult:
    run_id = latest_run_id(session)
    if run_id is None:
        return ScreenResult(items=[], total=0, page=req.page, page_size=req.page_size, ingestion_run_id=None)
    q, ordering = _query(req, run_id)
    total = session.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = session.execute(q.order_by(ordering, Scheme.id).offset((req.page - 1) * req.page_size).limit(req.page_size)).all()
    symbols = dict(
        session.execute(
            select(ExternalId.scheme_id, ExternalId.value).where(
                ExternalId.id_type == "yahoo_symbol", ExternalId.scheme_id.in_([r.id for r in rows])
            )
        ).all()
    )
    items = [ScreenRow(symbol=symbols.get(r.id), **r._asdict()) for r in rows]
    return ScreenResult(items=items, total=total, page=req.page, page_size=req.page_size, ingestion_run_id=run_id)


@router.post("/export")
def export_csv(req: ScreenRequest, session: Annotated[Session, Depends(get_session)]) -> Response:
    run_id = latest_run_id(session)
    if run_id is None:
        raise HTTPException(404, "no data ingested")
    q, ordering = _query(req, run_id)
    rows = session.execute(q.order_by(ordering, Scheme.id).limit(EXPORT_CAP + 1)).all()
    truncated = len(rows) > EXPORT_CAP
    rows = rows[:EXPORT_CAP]
    buf = io.StringIO()
    w = csv.writer(buf)
    cols = list(rows[0]._fields) if rows else ["id", "name"]
    w.writerow(cols)
    for r in rows:
        w.writerow([_safe(v) for v in r])
    return Response(
        buf.getvalue(), media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="screen.csv"',
            "X-Truncated": "true" if truncated else "false",
            "X-Ingestion-Run": str(run_id),
        },
    )
