from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from quant_engine import backtest as bt
from quant_engine import scoring
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import BacktestRun, FundCategory, FundScore, Scheme
from app.services import quant

router = APIRouter(prefix="/api/v1", tags=["quant"])

FACTOR_LABELS = {"performance": "Performance", "risk_adjusted": "Risk-adjusted returns", "consistency": "Consistency",
                 "downside": "Downside protection", "momentum": "Momentum", "stability": "Fund stability"}


@router.get("/quant/methodology")
def methodology() -> dict[str, Any]:
    return {
        "version": scoring.SCORE_VERSION,
        "weights": scoring.WEIGHTS,
        "factor_labels": FACTOR_LABELS,
        "metrics": [{"key": m.key, "factor": m.factor, "label": m.label, "higher_is_better": m.higher_is_better} for m in scoring.METRICS],
        "unavailable": {"stability": "Needs AUM history, expense ratios and manager tenure; none is connected. The other weights are renormalised per fund and coverage is shown."},
        "rules": [
            f"Funds are scored only against peers in the same category and plan (at least {scoring.MIN_PEERS} peers).",
            "Each metric is winsorised at the 5th/95th percentile, ranked 0-100 within the peer group (direction-aware) and z-scored.",
            "A factor score is the mean percentile of its available metrics; the composite weights available factors, renormalised.",
            f"A fund needs at least {int(scoring.MIN_COVERAGE * 100)}% of the total weight available to receive a composite; missing metrics are never filled with zero.",
            "Weights are research hypotheses, not tuned on this data. Scores are research indicators, not predictions or advice.",
            "Evidence so far (2026-11 build, survivors only): factor rank IC is positive for momentum, performance and consistency, but backtests of rule-based selection, including the composite, did not beat holding every comparable fund after costs, and the downside-protection factor showed no positive link to later peer-relative returns. See Factor Research and Strategy Backtesting.",
        ],
        "strategies": bt.STRATEGIES,
    }


@router.get("/quant/groups")
def groups(session: Annotated[Session, Depends(get_session)]) -> list[dict[str, Any]]:
    rows = session.execute(select(FundScore.peer_group, func.count(), func.count(FundScore.composite)).group_by(FundScore.peer_group).order_by(FundScore.peer_group)).all()
    return [{"group": g, "funds": n, "scored": s} for g, n, s in rows]


@router.get("/quant/scores")
def scores(
    session: Annotated[Session, Depends(get_session)],
    group: str | None = None, tier: str | None = None, q: str | None = Query(None, max_length=100),
    scored_only: bool = True, primary_only: bool = False,
    sort: str = "composite", order: str = "desc", page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    if sort not in ("composite", "coverage", "rank_in_group", "name"):
        raise HTTPException(422, "sort must be composite, coverage, rank_in_group or name")
    base = select(FundScore, Scheme.name, FundCategory.name, Scheme.plan_type, Scheme.asset_tier, Scheme.family_id).join(Scheme, Scheme.id == FundScore.scheme_id).join(
        FundCategory, FundCategory.id == Scheme.category_id)
    if group:
        base = base.where(FundScore.peer_group == group)
    if tier:
        base = base.where(Scheme.asset_tier == tier)
    if q:
        base = base.where(func.lower(Scheme.name).like(f"%{q.lower()}%"))
    if scored_only:
        base = base.where(FundScore.composite.is_not(None))
    if primary_only:  # one class per family: Direct preferred
        base = base.where(Scheme.plan_type == "Direct")
    total = session.scalar(select(func.count()).select_from(base.subquery())) or 0
    col = {"composite": FundScore.composite, "coverage": FundScore.coverage, "rank_in_group": FundScore.rank_in_group, "name": Scheme.name}[sort]
    ordering = col.desc().nulls_last() if order == "desc" else col.asc().nulls_last()
    rows = session.execute(base.order_by(ordering, FundScore.scheme_id).offset((page - 1) * page_size).limit(page_size)).all()
    items = [
        {"scheme_id": f.scheme_id, "name": name, "category": cat, "plan_type": plan, "asset_tier": tier, "peer_group": f.peer_group, "peers": f.peers,
         "composite": f.composite, "coverage": f.coverage, "rank_in_group": f.rank_in_group, "factors": f.detail["factors"]}
        for f, name, cat, plan, tier, _ in rows
    ]
    asof = session.scalar(select(func.max(FundScore.as_of)))
    return {"items": items, "total": total, "page": page, "page_size": page_size, "as_of": asof.date().isoformat() if asof else None,
            "methodology_version": scoring.SCORE_VERSION}


@router.get("/quant/scores/{scheme_id}")
def score_detail(scheme_id: int, session: Annotated[Session, Depends(get_session)]) -> dict[str, Any]:
    f = session.get(FundScore, scheme_id)
    s = session.get(Scheme, scheme_id)
    if s is None:
        raise HTTPException(404, "fund not found")
    if f is None:
        return {"available": False, "scheme_id": scheme_id, "name": s.name,
                "reason": "No score: only Growth schemes with a confirmed link to official NAV records and at least 3 years of history are scored."}
    d = f.detail
    metrics = [
        {"key": m.key, "label": m.label, "factor": m.factor, "higher_is_better": m.higher_is_better, "raw": d["metrics"].get(m.key),
         "percentile": d["percentiles"].get(m.key), "z": d["z"].get(m.key)}
        for m in scoring.METRICS
    ]
    return {
        "available": True, "scheme_id": scheme_id, "name": s.name, "as_of": f.as_of.date().isoformat(), "methodology_version": f.methodology_version,
        "peer_group": f.peer_group, "peers": f.peers, "composite": f.composite, "coverage": f.coverage, "rank_in_group": f.rank_in_group,
        "scored": f.composite is not None,
        "not_scored_reason": None if f.composite is not None else "Too few metrics available for this fund, or too few peers in its group.",
        "factors": [{"key": k, "label": FACTOR_LABELS[k], "weight": scoring.WEIGHTS[k], "score": d["factors"].get(k), "contribution": d["contributions"].get(k)}
                    for k in scoring.FACTORS],
        "metrics": metrics, "extra": {"vol_3y": d["metrics"].get("vol_3y")},
        "caveat": "A research indicator relative to peers, not a prediction. Stability is unavailable and the other weights are renormalised.",
    }


def _file(name: str, key: str | None = None) -> dict[str, Any]:
    out = quant.read_json(name)
    if out is None:
        raise HTTPException(404, "not built yet; run `python -m app.cli.pipeline quant`")
    return out[key] if key else out


@router.get("/quant/factors")
def factors() -> dict[str, Any]:
    return _file("factors.json", "factors")


@router.get("/quant/statistics")
def statistics() -> dict[str, Any]:
    return _file("factors.json", "statistics")


@router.get("/quant/clusters")
def clusters() -> dict[str, Any]:
    return _file("clusters.json")


@router.get("/quant/regimes")
def regimes() -> dict[str, Any]:
    return _file("regimes.json")


# ---------------------------------------------------------------- backtests (jobs)
@router.post("/quant/backtests", status_code=202)
def create_backtest(req: dict[str, Any], session: Annotated[Session, Depends(get_session)]) -> JSONResponse:
    try:
        run = quant.submit(session, req)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(409, str(exc)) from exc
    except quant.BacktestsDisabled as exc:
        raise HTTPException(503, str(exc)) from exc
    return JSONResponse({"id": run.id, "status": run.status, "poll": f"/api/v1/jobs/{run.id}", "result": f"/api/v1/quant/backtests/{run.id}"}, status_code=202)


@router.get("/jobs/{run_id}")
def job(run_id: int, session: Annotated[Session, Depends(get_session)]) -> dict[str, Any]:
    run = session.get(BacktestRun, run_id)
    if run is None:
        raise HTTPException(404, "job not found")
    return {"id": run.id, "status": run.status, "error": run.error, "created_at": run.created_at.isoformat(),
            "finished_at": run.finished_at.isoformat() if run.finished_at else None}


@router.get("/quant/backtests/{run_id}")
def backtest_result(run_id: int, session: Annotated[Session, Depends(get_session)]) -> dict[str, Any]:
    run = session.get(BacktestRun, run_id)
    if run is None:
        raise HTTPException(404, "backtest not found")
    if run.status != "succeeded":
        raise HTTPException(409, f"backtest is {run.status}" + (f": {run.error}" if run.error else ""))
    return {"id": run.id, "request": run.request, **(run.result or {})}


@router.get("/amcs")
def amc_ranking(session: Annotated[Session, Depends(get_session)]) -> dict[str, Any]:
    from app.services import amc

    return amc.ranking(session)


@router.get("/amcs/{amc_id}")
def amc_detail(amc_id: int, session: Annotated[Session, Depends(get_session)]) -> dict[str, Any]:
    from app.services import amc

    d = amc.detail(session, amc_id)
    if d is None:
        raise HTTPException(404, "AMC not found or has no Direct Growth funds")
    return d
