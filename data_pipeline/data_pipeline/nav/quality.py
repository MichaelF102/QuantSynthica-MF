"""Quality checks for a single NAV series. Issues are reported; suspicious values are flagged, never deleted.

Conflicting duplicate dates are the one case where a value is withheld from the clean series, because
choosing one silently would be arbitrary.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta

GAP_DAYS = 10  # calendar days between consecutive observations before a gap is reported
JUMP_PCT = 0.20  # one-observation move that is flagged as suspicious
STALE_RUN = 30  # identical consecutive NAVs


@dataclass(frozen=True)
class NavIssue:
    rule: str
    severity: str
    detail: dict


def check_series(obs: Sequence[tuple[date, float | None]], today: date | None = None) -> tuple[list[tuple[date, float]], list[NavIssue]]:
    """`obs` in any order. Returns (clean ascending series, issues)."""
    issues: list[NavIssue] = []
    today = today or date.today()
    by_date: dict[date, list[float | None]] = {}
    for d, v in obs:
        by_date.setdefault(d, []).append(v)

    clean: list[tuple[date, float]] = []
    for d in sorted(by_date):
        vals = by_date[d]
        valid = [v for v in vals if v is not None and v > 0]
        if len(vals) - len(valid):
            issues.append(NavIssue("N010_invalid_nav", "error", {"date": d.isoformat(), "values": [str(v) for v in vals]}))
        if d > today + timedelta(days=1):
            issues.append(NavIssue("N011_future_date", "warning", {"date": d.isoformat()}))
        if not valid:
            continue
        if len(set(valid)) > 1:
            issues.append(NavIssue("N012_conflicting_duplicate", "error", {"date": d.isoformat(), "values": valid}))
            continue  # withheld: cannot pick one without guessing
        if len(vals) > 1:
            issues.append(NavIssue("N013_duplicate_same_value", "info", {"date": d.isoformat(), "count": len(vals)}))
        clean.append((d, valid[0]))

    for (d0, v0), (d1, v1) in zip(clean, clean[1:]):
        gap = (d1 - d0).days
        if gap > GAP_DAYS:
            issues.append(NavIssue("N020_gap", "warning", {"from": d0.isoformat(), "to": d1.isoformat(), "days": gap}))
        if v0 and abs(v1 / v0 - 1) > JUMP_PCT:
            issues.append(NavIssue("N021_large_move", "warning", {"from": d0.isoformat(), "to": d1.isoformat(), "pct": round((v1 / v0 - 1) * 100, 2)}))

    run, start = 1, None
    for i in range(1, len(clean)):
        if clean[i][1] == clean[i - 1][1]:
            run += 1
            start = start or clean[i - 1][0]
        else:
            if run >= STALE_RUN and start:
                issues.append(NavIssue("N022_stale_run", "info", {"from": start.isoformat(), "obs": run}))
            run, start = 1, None
    if run >= STALE_RUN and start:
        issues.append(NavIssue("N022_stale_run", "info", {"from": start.isoformat(), "obs": run}))
    return clean, issues
