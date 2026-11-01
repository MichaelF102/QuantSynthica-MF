from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_session
from app.services import analytics

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])
MAX_COMPARE = 5


def _years(v: str) -> float | None:
    if v == "max":
        return None
    try:
        y = float(v)
    except ValueError as exc:
        raise HTTPException(422, "years must be a number or 'max'") from exc
    if not 0.25 <= y <= 30:
        raise HTTPException(422, "years must be between 0.25 and 30")
    return y


@router.get("/compare")
def compare(session: Annotated[Session, Depends(get_session)], ids: str, years: str = "3") -> dict[str, Any]:
    try:
        wanted = list(dict.fromkeys(int(x) for x in ids.split(",") if x.strip()))
    except ValueError as exc:
        raise HTTPException(422, "ids must be integers") from exc
    if not 1 <= len(wanted) <= MAX_COMPARE:
        raise HTTPException(422, f"choose between 1 and {MAX_COMPARE} funds")
    return analytics.compare_analytics(session, wanted, _years(years))


@router.get("/{scheme_id}")
def fund(scheme_id: int, session: Annotated[Session, Depends(get_session)], years: str = Query("3")) -> dict[str, Any]:
    out = analytics.fund_analytics(session, scheme_id, _years(years))
    if out is None:
        raise HTTPException(404, "fund not found")
    return out
