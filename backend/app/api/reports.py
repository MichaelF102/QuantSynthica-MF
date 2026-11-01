from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db import get_session
from app.services import reports as svc

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])
TYPES = {"xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "pdf": "application/pdf"}


@router.post("/{kind}.{fmt}")
def report(kind: str, fmt: str, params: dict[str, Any], session: Annotated[Session, Depends(get_session)]) -> Response:
    if fmt not in TYPES:
        raise HTTPException(422, "format must be pdf or xlsx")
    try:
        rep = svc.build(session, kind, params)
    except svc.ReportError as exc:
        raise HTTPException(422, str(exc)) from exc
    body = svc.to_pdf(rep) if fmt == "pdf" else svc.to_xlsx(rep)
    return Response(body, media_type=TYPES[fmt], headers={"Content-Disposition": f'attachment; filename="qsmf-{kind}-report.{fmt}"'})
