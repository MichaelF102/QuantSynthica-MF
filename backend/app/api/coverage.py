import json
from typing import Any

from fastapi import APIRouter, HTTPException

from app.services.coverage import report_path

router = APIRouter(prefix="/api/v1", tags=["coverage"])


@router.get("/data-coverage")
def data_coverage() -> dict[str, Any]:
    """Mapping and NAV-history coverage, produced by `python -m app.cli.pipeline coverage`."""
    p = report_path()
    if not p.exists():
        raise HTTPException(404, "coverage report has not been generated yet")
    return json.loads(p.read_text())
