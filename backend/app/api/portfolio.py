from typing import Annotated, Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_session
from app.services import portfolio as svc

router = APIRouter(prefix="/api/v1/portfolio", tags=["portfolio"])


def _run(fn: Callable[[Session, dict], dict], session: Session, req: dict[str, Any]) -> dict[str, Any]:
    try:
        return fn(session, req)
    except svc.RequestError as exc:
        raise HTTPException(422, str(exc)) from exc
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(422, f"invalid request: {exc}") from exc
    except FileNotFoundError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/funds")
def eligible_funds(session: Annotated[Session, Depends(get_session)], q: str = Query("", max_length=80), limit: int = Query(15, ge=1, le=50),
                   ids: str = Query("", max_length=400)) -> list[dict[str, Any]]:
    """Funds that can go into a portfolio (Growth, confirmed NAV link, clean history), searched by name."""
    from app.services import lite

    uni = lite.universe(session)
    needle = q.strip().lower()
    if ids.strip():
        try:
            want = [int(x) for x in ids.split(",") if x.strip()]
        except ValueError as exc:
            raise HTTPException(422, "ids must be integers") from exc
        df = uni[uni["scheme_id"].isin(want)].set_index("scheme_id").loc[[i for i in want if i in set(uni["scheme_id"])]].reset_index()
    else:
        df = uni[uni["name"].str.lower().str.contains(needle, regex=False)] if needle else uni
        df = df.sort_values("name").head(limit)
    return [{"scheme_id": int(r.scheme_id), "name": r.name, "category": r.category, "plan": r.plan, "tier": r.tier} for r in df.itertuples()]


@router.get("/methods")
def methods() -> dict[str, str]:
    return svc.METHODS


@router.post("/analyze")
def analyze(req: dict[str, Any], session: Annotated[Session, Depends(get_session)]) -> dict[str, Any]:
    return _run(svc.analyze, session, req)


@router.post("/optimize")
def optimize(req: dict[str, Any], session: Annotated[Session, Depends(get_session)]) -> dict[str, Any]:
    return _run(svc.optimize, session, req)


@router.post("/simulate")
def simulate(req: dict[str, Any], session: Annotated[Session, Depends(get_session)]) -> dict[str, Any]:
    return _run(svc.simulate, session, req)


@router.post("/rebalance")
def rebalance(req: dict[str, Any], session: Annotated[Session, Depends(get_session)]) -> dict[str, Any]:
    return _run(svc.rebalance, session, req)


@router.post("/stress")
def stress(req: dict[str, Any], session: Annotated[Session, Depends(get_session)]) -> dict[str, Any]:
    return _run(svc.stress, session, req)
