"""Shared conventions and helpers.

Conventions (recorded in every result, see `conventions()`):
- Series are NAVs indexed by observation date, ascending. NAV is a price series of a Growth option, so
  returns are total returns. IDCW options are NOT supported (distributions are not in the series).
- Period returns are simple returns between consecutive observations. A return that spans more than
  MAX_GAP_DAYS calendar days is dropped rather than treated as a one-day return.
- Annualisation: 252 periods for daily statistics; 365.25 calendar days for CAGR.
- Windows end on the last observation on or before the end date; a window start is the last observation on
  or before the start date, at most START_TOLERANCE_DAYS earlier. Otherwise the window is unavailable.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date

import numpy as np
import pandas as pd

from quant_engine import METHODOLOGY_VERSION

TRADING_DAYS = 252
CALENDAR_DAYS = 365.25
MAX_GAP_DAYS = 5
START_TOLERANCE_DAYS = 7
MIN_OBS = 30
SUSPECT_MOVE = 0.25  # a one-observation NAV move beyond this is treated as a probable unit split or data error
MIN_RATIO_VOL = 0.5  # % p.a.: below this, ratios with volatility in the denominator are not meaningful


@dataclass(frozen=True)
class Metric:
    """A computed value with its provenance. `value` is None when it cannot be computed; `note` says why."""

    name: str
    value: float | None
    unit: str  # "%", "ratio", "days", ...
    window_start: date | None = None
    window_end: date | None = None
    n_obs: int = 0
    coverage: float | None = None  # observations / expected observations in the window, capped at 1
    note: str | None = None
    methodology_version: str = METHODOLOGY_VERSION

    def to_dict(self) -> dict:
        d = asdict(self)
        d["window_start"] = self.window_start.isoformat() if self.window_start else None
        d["window_end"] = self.window_end.isoformat() if self.window_end else None
        return d


def conventions(rf: str = "none", benchmark: str = "none") -> dict:
    return {
        "return_type": "simple, between consecutive NAV observations", "max_gap_days": MAX_GAP_DAYS,
        "annualisation_periods": TRADING_DAYS, "cagr_days": CALENDAR_DAYS, "risk_free": rf, "benchmark": benchmark,
        "methodology_version": METHODOLOGY_VERSION,
    }


def clean_nav(nav: pd.Series) -> pd.Series:
    """Sorted, de-duplicated, positive, finite NAV with a DatetimeIndex (no values are altered)."""
    s = nav.copy()
    s.index = pd.DatetimeIndex(s.index)
    s = s[~s.index.duplicated(keep="last")].sort_index()
    s = s[np.isfinite(s.to_numpy(dtype=float)) & (s > 0)]
    return s.astype(float)


def suspect_moves(nav: pd.Series, threshold: float = SUSPECT_MOVE, max_gap_days: int = MAX_GAP_DAYS) -> list[tuple[pd.Timestamp, float]]:
    """Observations where NAV jumps by more than `threshold` versus the previous observation (date, move as a fraction).

    Only observations at most `max_gap_days` apart are compared: a change across a long hole in the data is
    unknown, not a one-day move, and `returns()` already drops it. Mutual-fund NAVs essentially never move 25% in a
    day except on a unit split/consolidation or a data error. Nothing is corrected here: callers must exclude
    affected windows or funds until the event is verified.
    """
    nav = clean_nav(nav)
    if len(nav) < 2:
        return []
    mv = nav.pct_change()
    gap = pd.Series(nav.index, index=nav.index).diff().dt.days
    mv = mv[(gap <= max_gap_days)].dropna()
    bad = mv[mv.abs() > threshold]
    return [(ts, float(v)) for ts, v in bad.items()]


def returns(nav: pd.Series, max_gap_days: int = MAX_GAP_DAYS) -> pd.Series:
    """Simple period returns; returns spanning more than `max_gap_days` calendar days are dropped."""
    nav = clean_nav(nav)
    r = nav.pct_change().dropna()
    gaps = pd.Series((nav.index[1:] - nav.index[:-1]).days, index=nav.index[1:])
    return r[gaps.reindex(r.index) <= max_gap_days]


def anchor(nav: pd.Series, target: pd.Timestamp, tolerance_days: int = START_TOLERANCE_DAYS) -> tuple[pd.Timestamp, float] | None:
    """Last observation on or before `target`, at most `tolerance_days` earlier."""
    pos = nav.index.searchsorted(target, side="right") - 1
    if pos < 0:
        return None
    ts = nav.index[pos]
    return (ts, float(nav.iloc[pos])) if (target - ts).days <= tolerance_days else None


def years_back(ts: pd.Timestamp, years: float) -> pd.Timestamp:
    if float(years).is_integer():
        try:
            return ts.replace(year=ts.year - int(years))
        except ValueError:  # 29 February
            return ts.replace(year=ts.year - int(years), day=28)
    return ts - pd.Timedelta(days=round(years * CALENDAR_DAYS))


def coverage(n_obs: int, start: pd.Timestamp, end: pd.Timestamp) -> float:
    """Observations versus the ~252/365.25 trading days expected in the window."""
    days = max((end - start).days, 1)
    return min(1.0, n_obs / (days * TRADING_DAYS / CALENDAR_DAYS))


def align(a: pd.Series, b: pd.Series) -> tuple[pd.Series, pd.Series]:
    idx = a.index.intersection(b.index)
    return a.loc[idx], b.loc[idx]


def period_rf(rf: pd.Series | float | None, index: pd.DatetimeIndex) -> pd.Series:
    """Per-period risk-free return aligned to `index`. A float is an annual rate converted geometrically per period."""
    if rf is None:
        return pd.Series(0.0, index=index)
    if isinstance(rf, pd.Series):
        return rf.reindex(index).astype(float)
    return pd.Series((1 + float(rf)) ** (1 / TRADING_DAYS) - 1, index=index)


def window_slice(nav: pd.Series, end: pd.Timestamp | None, years: float | None) -> tuple[pd.Series, str | None]:
    """NAV between the window start anchor and the end. Returns (series, reason-if-unavailable)."""
    nav = clean_nav(nav)
    if nav.empty:
        return nav, "no data"
    end_ts = nav.index[nav.index.searchsorted(end, side="right") - 1] if end is not None else nav.index[-1]
    if years is None:
        return nav.loc[:end_ts], None
    a = anchor(nav, years_back(end_ts, years))
    if a is None:
        return nav.iloc[0:0], f"less than {years:g}y of history"
    return nav.loc[a[0]:end_ts], None
