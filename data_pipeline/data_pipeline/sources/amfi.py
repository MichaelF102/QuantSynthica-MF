"""Parser and fetcher for AMFI NAV text files (latest NAV and date-range history).

Both files are semicolon separated with section lines (category, AMC) between data rows. The two
formats order their columns differently, so columns are always read from the header row.
"""
from __future__ import annotations

import math
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from data_pipeline.http import fetch

NAV_ALL_URL = "https://portal.amfiindia.com/spages/NAVAll.txt"
HISTORY_URL = "https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx?frmdt={frm}&todt={to}"
MAX_HISTORY_DAYS = 90  # a one-year range returned an HTML error page; 90 days worked (~70 MB)
_CATEGORY = re.compile(r"^(Open Ended|Close Ended|Interval Fund)\b", re.IGNORECASE)


@dataclass(frozen=True)
class AmfiRecord:
    code: str
    name: str
    plan: str | None
    option: str | None
    isin_primary: str | None  # payout (IDCW) or growth ISIN
    isin_reinvest: str | None
    nav: float | None
    nav_date: date | None
    amc: str | None
    category: str | None


def _clean(v: str | None) -> str | None:
    v = (v or "").strip()
    return None if v in ("", "-", "N.A.", "NA") else v


def _parse_nav(v: str | None) -> float | None:
    v = _clean(v)
    if v is None:
        return None
    try:
        x = float(v.replace(",", ""))
    except ValueError:
        return None
    return x if math.isfinite(x) else None


def _parse_date(v: str | None) -> date | None:
    v = _clean(v)
    if v is None:
        return None
    for fmt in ("%d-%b-%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            continue
    return None


def _norm_header(h: str) -> str:
    h = re.sub(r"\s+", " ", h.strip().lower())
    if h == "scheme code":
        return "code"
    if h in ("scheme name", "nav name"):
        return "name"
    if h == "plan":
        return "plan"
    if h == "option":
        return "option"
    if h.startswith("isin div payout"):
        return "isin_primary"
    if h.startswith("isin div reinvestment"):
        return "isin_reinvest"
    if h in ("net asset value", "nav"):
        return "nav"
    if h == "date":
        return "date"
    return h


def parse(text: str) -> Iterator[AmfiRecord]:
    cols: list[str] | None = None
    amc: str | None = None
    category: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if ";" not in line:
            if _CATEGORY.match(line):
                m = re.search(r"\((.*)\)\s*$", line)
                category = (m.group(1) if m else line).strip()
            elif line.startswith("<"):
                raise ValueError("received HTML instead of NAV data")
            else:
                amc = line
            continue
        parts = [p.strip() for p in line.split(";")]
        if parts[0].lower() == "scheme code":
            cols = [_norm_header(p) for p in parts]
            continue
        if cols is None or len(parts) < len(cols):
            continue
        row = dict(zip(cols, parts))
        code = _clean(row.get("code"))
        if not code or not code.isdigit():
            continue
        yield AmfiRecord(
            code=code, name=row.get("name", ""), plan=_clean(row.get("plan")), option=_clean(row.get("option")),
            isin_primary=_clean(row.get("isin_primary")), isin_reinvest=_clean(row.get("isin_reinvest")),
            nav=_parse_nav(row.get("nav")), nav_date=_parse_date(row.get("date")), amc=amc, category=category,
        )


def _validate_text(body: bytes) -> None:
    head = body[:2000].lstrip().lower()
    if head.startswith(b"<!doctype") or head.startswith(b"<html"):
        raise ValueError("HTML response instead of NAV data")
    if b"scheme code" not in body[:2000].lower():
        raise ValueError("unexpected response: no header row")


def fetch_nav_all() -> tuple[bytes, list[AmfiRecord]]:
    body = fetch(NAV_ALL_URL, timeout=90, validate=_validate_text)
    return body, list(parse(body.decode("utf-8", errors="replace")))


def history_windows(start: date, end: date, days: int = MAX_HISTORY_DAYS) -> Iterable[tuple[date, date]]:
    cur = start
    while cur <= end:
        stop = min(cur + timedelta(days=days - 1), end)
        yield cur, stop
        cur = stop + timedelta(days=1)


def fetch_history(frm: date, to: date) -> tuple[bytes, list[AmfiRecord]]:
    if (to - frm).days + 1 > MAX_HISTORY_DAYS:
        raise ValueError(f"range longer than {MAX_HISTORY_DAYS} days")
    url = HISTORY_URL.format(frm=frm.strftime("%d-%b-%Y"), to=to.strftime("%d-%b-%Y"))
    body = fetch(url, timeout=240, validate=_validate_text)
    return body, list(parse(body.decode("utf-8", errors="replace")))
