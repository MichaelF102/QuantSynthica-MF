from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.account import CurrentUser
from app.db import get_session
from app.services import assistant as svc

router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])


@router.post("/ask")
def ask(body: dict[str, Any], session: Annotated[Session, Depends(get_session)], user: CurrentUser) -> dict[str, Any]:
    """Private: requires sign-in. Every call is logged with the tools used (audit) but not the answer text."""
    q = str(body.get("question", ""))
    a = svc.ask(session, q, svc.default_llm())
    svc.log.info("assistant_call user=%s refused=%s reason=%s tools=%s facts=%d", user.id, a.refused, a.refusal_reason,
                 [(t.name, t.ok) for t in a.tool_calls], len(a.facts))
    return asdict(a)
