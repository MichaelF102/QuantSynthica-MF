"""Client for mfapi.in (community-run JSON wrapper over AMFI data). No SLA: validate and cache everything."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime

from data_pipeline.http import fetch

BASE = "https://api.mfapi.in"


@dataclass(frozen=True)
class SchemeHistory:
    code: str
    meta: dict
    observations: list[tuple[date, float | None, str]]  # (date, nav, raw_nav_string), ascending by date
    raw: bytes


def _validate_json(body: bytes) -> None:
    obj = json.loads(body)  # a truncated body raises ValueError -> retried by fetch()
    if not isinstance(obj, dict) or "data" not in obj or "meta" not in obj:
        raise ValueError("unexpected mfapi payload")


def fetch_scheme_history(code: str) -> SchemeHistory:
    # Some legacy codes hang; fail fast and let the resumable backfill retry later
    body = fetch(f"{BASE}/mf/{int(code)}", timeout=20, retries=2, backoff=1.0, validate=_validate_json)
    return parse_history(code, body)


def parse_history(code: str, body: bytes) -> SchemeHistory:
    obj = json.loads(body)
    obs: list[tuple[date, float | None, str]] = []
    for row in obj.get("data", []):
        raw = str(row.get("nav", "")).strip()
        try:
            d = datetime.strptime(str(row.get("date", "")).strip(), "%d-%m-%Y").date()
        except ValueError:
            continue
        try:
            nav = float(raw)
        except ValueError:
            nav = None
        obs.append((d, nav, raw))
    obs.sort(key=lambda t: t[0])
    return SchemeHistory(code=str(code), meta=obj.get("meta", {}), observations=obs, raw=body)
