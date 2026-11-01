"""Operations endpoint for a scheduler (Render cron job). Disabled unless QSMF_ADMIN_TOKEN is set.

Render persistent disks attach to ONE service, so the data refresh must run inside the API service; a cron job just calls this.
"""
import hmac
import json
import subprocess
import sys
import threading
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Header, HTTPException

from app.core.config import get_settings

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
STEPS = [["recent", "--days", "7"], ["metrics"], ["quant"]]
_lock = threading.Lock()
_state: dict[str, Any] = {"running": False, "started": None, "finished": None, "ok": None, "failed_step": None, "log_tail": ""}


def _check(token: str | None) -> None:
    expected = get_settings().admin_token
    if not expected:
        raise HTTPException(404, "not found")  # feature off: do not reveal it exists
    if not token or not hmac.compare_digest(token, expected):
        raise HTTPException(401, "invalid admin token")


def _run() -> None:
    tail: list[str] = []
    ok, failed = True, None
    for step in STEPS:
        p = subprocess.run([sys.executable, "-m", "app.cli.pipeline", *step], capture_output=True, text=True)
        tail = (p.stdout + p.stderr).splitlines()[-15:]
        if p.returncode != 0:
            ok, failed = False, step[0]
            break
    _state.update(running=False, finished=datetime.now(UTC).isoformat(), ok=ok, failed_step=failed, log_tail="\n".join(tail))
    _lock.release()


@router.post("/refresh", status_code=202)
def refresh(x_admin_token: Annotated[str | None, Header()] = None) -> dict[str, Any]:
    _check(x_admin_token)
    if not _lock.acquire(blocking=False):
        raise HTTPException(409, "a refresh is already running")
    _state.update(running=True, started=datetime.now(UTC).isoformat(), finished=None, ok=None, failed_step=None, log_tail="")
    threading.Thread(target=_run, daemon=True).start()
    return {"started": True}


@router.get("/refresh")
def status(x_admin_token: Annotated[str | None, Header()] = None) -> dict[str, Any]:
    _check(x_admin_token)
    return json.loads(json.dumps(_state))
