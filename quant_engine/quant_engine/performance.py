"""Performance analytics from NAV series. Pure functions; see common.py for conventions."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from quant_engine.common import (
    CALENDAR_DAYS,
    MIN_OBS,
    START_TOLERANCE_DAYS,
    TRADING_DAYS,
    Metric,
    align,
    anchor,
    clean_nav,
    coverage,
    returns,
    window_slice,
    years_back,
)


def _m(name: str, value: float | None, unit: str, nav: pd.Series | None = None, note: str | None = None, n: int | None = None) -> Metric:
    if nav is None or nav.empty:
        return Metric(name, value, unit, note=note)
    return Metric(name, value, unit, nav.index[0].date(), nav.index[-1].date(), n if n is not None else len(nav),
                  coverage(len(nav), nav.index[0], nav.index[-1]), note)


# ---------------------------------------------------------------- point-to-point
def total_return(nav: pd.Series) -> Metric:
    nav = clean_nav(nav)
    if len(nav) < 2:
        return _m("total_return", None, "%", nav, "fewer than 2 observations")
    return _m("total_return", (nav.iloc[-1] / nav.iloc[0] - 1) * 100, "%", nav)


def cagr(nav: pd.Series) -> Metric:
    nav = clean_nav(nav)
    if len(nav) < MIN_OBS:
        return _m("cagr", None, "%", nav, f"fewer than {MIN_OBS} observations")
    days = (nav.index[-1] - nav.index[0]).days
    if days < 30:
        return _m("cagr", None, "%", nav, "window shorter than 30 days")
    return _m("cagr", ((nav.iloc[-1] / nav.iloc[0]) ** (CALENDAR_DAYS / days) - 1) * 100, "%", nav)


def trailing_returns(nav: pd.Series, end: pd.Timestamp | None = None) -> dict[str, Metric]:
    """1M, 3M, 6M, YTD (cumulative) and 1Y, 3Y, 5Y, 10Y (annualised, CAGR). Missing history -> value None with a reason."""
    nav = clean_nav(nav)
    out: dict[str, Metric] = {}
    if nav.empty:
        return out
    end_ts = nav.index[nav.index.searchsorted(end, side="right") - 1] if end is not None else nav.index[-1]
    last = float(nav.loc[end_ts])
    spec: list[tuple[str, pd.Timestamp, float | None]] = [
        ("1m", end_ts - pd.DateOffset(months=1), None), ("3m", end_ts - pd.DateOffset(months=3), None),
        ("6m", end_ts - pd.DateOffset(months=6), None), ("ytd", pd.Timestamp(end_ts.year - 1, 12, 31), None),
        ("1y", years_back(end_ts, 1), 1), ("3y", years_back(end_ts, 3), 3), ("5y", years_back(end_ts, 5), 5),
        ("10y", years_back(end_ts, 10), 10),
    ]
    for label, target, yrs in spec:
        a = anchor(nav.loc[:end_ts], target)
        if a is None:
            out[label] = Metric(f"return_{label}", None, "%", window_end=end_ts.date(), note="not enough history")
            continue
        ratio = last / a[1]
        val = ((ratio ** (1 / yrs)) - 1) * 100 if yrs else (ratio - 1) * 100
        sub = nav.loc[a[0]:end_ts]
        out[label] = Metric(f"return_{label}", val, "% p.a." if yrs else "%", a[0].date(), end_ts.date(), len(sub),
                            coverage(len(sub), a[0], end_ts), None)
    return out


# ---------------------------------------------------------------- rolling
def rolling_returns(nav: pd.Series, years: float) -> pd.Series:
    """Return over each trailing `years` window ending at every observation date (annualised if years > 1).

    A window exists only when an observation is available within START_TOLERANCE_DAYS before the window start.
    """
    nav = clean_nav(nav)
    if nav.empty:
        return pd.Series(dtype=float)
    idx = nav.index
    targets = pd.DatetimeIndex([years_back(t, years) for t in idx])
    pos = idx.searchsorted(targets, side="right") - 1
    ok = pos >= 0
    safe = np.where(ok, pos, 0)
    gap = (targets - idx[safe]).days
    ok &= gap <= START_TOLERANCE_DAYS
    ratio = nav.to_numpy() / nav.to_numpy()[safe]
    vals = (ratio ** (1 / years) - 1) * 100 if years > 1 else (ratio - 1) * 100
    return pd.Series(vals, index=idx)[ok]


def rolling_summary(rolling: pd.Series) -> dict[str, float | int | None]:
    if rolling.empty:
        return {"n": 0, "median": None, "p5": None, "p95": None, "best": None, "worst": None, "pct_positive": None}
    return {
        "n": len(rolling), "median": float(rolling.median()), "p5": float(rolling.quantile(0.05)),
        "p95": float(rolling.quantile(0.95)), "best": float(rolling.max()), "worst": float(rolling.min()),
        "pct_positive": float((rolling > 0).mean() * 100),
    }


def outperformance_frequency(fund_roll: pd.Series, bench_roll: pd.Series) -> Metric:
    f, b = align(fund_roll, bench_roll)
    if len(f) < MIN_OBS:
        return Metric("pct_rolling_outperform", None, "%", n_obs=len(f), note="too few overlapping rolling windows")
    return Metric("pct_rolling_outperform", float((f > b).mean() * 100), "%", f.index[0].date(), f.index[-1].date(), len(f))


# ---------------------------------------------------------------- calendar
def calendar_returns(nav: pd.Series) -> list[dict]:
    """Per calendar year: last NAV of the year vs last NAV of the prior year. The first and current years are partial."""
    nav = clean_nav(nav)
    if len(nav) < 2:
        return []
    out = []
    years = sorted(set(nav.index.year))
    last_year = nav.index[-1].year
    for y in years:
        yr = nav[nav.index.year == y]
        base = anchor(nav, pd.Timestamp(y - 1, 12, 31))
        partial = False
        if base is None:
            base = (yr.index[0], float(yr.iloc[0]))  # fund (or data) starts inside this year
            partial = True
            if len(yr) < 2:
                continue  # one observation and no prior year-end: no return
        if y == last_year and nav.index[-1] < pd.Timestamp(y, 12, 24):
            partial = True  # year to date
        out.append({"year": int(y), "return": (float(yr.iloc[-1]) / base[1] - 1) * 100, "partial": partial,
                    "start": base[0].date().isoformat(), "end": yr.index[-1].date().isoformat()})
    return out


# ---------------------------------------------------------------- benchmark-relative
def tracking_error(r: pd.Series, b: pd.Series) -> Metric:
    r, b = align(r, b)
    if len(r) < MIN_OBS:
        return Metric("tracking_error", None, "%", n_obs=len(r), note=f"fewer than {MIN_OBS} overlapping observations")
    te = float((r - b).std(ddof=1) * math.sqrt(TRADING_DAYS) * 100)
    return Metric("tracking_error", te, "%", r.index[0].date(), r.index[-1].date(), len(r))


def information_ratio(r: pd.Series, b: pd.Series) -> Metric:
    r, b = align(r, b)
    if len(r) < MIN_OBS:
        return Metric("information_ratio", None, "ratio", n_obs=len(r), note=f"fewer than {MIN_OBS} overlapping observations")
    active = r - b
    sd = active.std(ddof=1)
    if not sd or not math.isfinite(sd) or sd < 1e-12:
        return Metric("information_ratio", None, "ratio", r.index[0].date(), r.index[-1].date(), len(r), note="zero tracking error")
    return Metric("information_ratio", float(active.mean() * TRADING_DAYS / (sd * math.sqrt(TRADING_DAYS))), "ratio",
                  r.index[0].date(), r.index[-1].date(), len(r))


def monthly_returns(nav: pd.Series) -> pd.Series:
    """Month-end to month-end returns (the last observation in each month)."""
    nav = clean_nav(nav)
    m = nav.groupby([nav.index.year, nav.index.month]).last()
    ends = nav.groupby([nav.index.year, nav.index.month]).apply(lambda s: s.index[-1])
    m.index = pd.DatetimeIndex(ends.values)
    return m.pct_change().dropna()


def capture_ratios(nav: pd.Series, bench_nav: pd.Series, min_months: int = 24) -> dict[str, Metric]:
    """Upside / downside capture from monthly returns (geometric average in up / down benchmark months)."""
    f, b = monthly_returns(nav), monthly_returns(bench_nav)
    f.index, b.index = f.index.to_period("M"), b.index.to_period("M")
    f, b = align(f, b)
    out = {}
    for name, mask in (("upside_capture", b > 0), ("downside_capture", b < 0)):
        fm, bm = f[mask], b[mask]
        if len(f) < min_months or len(bm) < 6:
            out[name] = Metric(name, None, "%", n_obs=len(f), note=f"fewer than {min_months} overlapping months or too few {'up' if 'up' in name else 'down'} months")
            continue
        fg = (1 + fm).prod() ** (1 / len(fm)) - 1
        bg = (1 + bm).prod() ** (1 / len(bm)) - 1
        out[name] = Metric(name, float(fg / bg * 100) if bg else None, "%", f.index[0].to_timestamp().date(),
                           f.index[-1].to_timestamp().date(), len(f), note=None if bg else "benchmark average is zero")
    return out


def positive_period_frequency(nav: pd.Series) -> Metric:
    m = monthly_returns(nav)
    if len(m) < 12:
        return Metric("pct_positive_months", None, "%", n_obs=len(m), note="fewer than 12 months")
    return Metric("pct_positive_months", float((m > 0).mean() * 100), "%", m.index[0].date(), m.index[-1].date(), len(m))


def window_returns(nav: pd.Series, end: pd.Timestamp | None, years: float | None) -> pd.Series:
    sl, _ = window_slice(nav, end, years)
    return returns(sl) if len(sl) > 1 else pd.Series(dtype=float)
