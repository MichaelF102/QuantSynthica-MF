"""Investment simulators, stress windows and rebalancing.

Two kinds of output, never mixed
- HISTORICAL simulation: what would have happened using the actual NAV history (`sip`, `lump_sum`, `swp`, rolling outcomes).
- HYPOTHETICAL projection: what could happen under assumed returns or resampled history (`projection`, `bootstrap_projection`).
  These are illustrations, not forecasts, and every result carries `kind` so a UI can label it.
"""
from __future__ import annotations

import math
from datetime import date

import numpy as np
import pandas as pd

SIM_VERSION = "simulate-1.0.0"


# --------------------------------------------------------------------------- XIRR
def xirr(flows: list[tuple[date, float]]) -> float | None:
    """Annualised internal rate of return of dated cash flows (outflows negative). None if it does not exist."""
    if len(flows) < 2 or not (any(a < 0 for _, a in flows) and any(a > 0 for _, a in flows)):
        return None
    t0 = flows[0][0]
    t = np.array([(d - t0).days / 365.0 for d, _ in flows])
    a = np.array([x for _, x in flows], dtype=float)

    def f(r: float) -> float:
        return float((a / (1 + r) ** t).sum())

    lo, hi = -0.9999, 10.0
    flo, fhi = f(lo), f(hi)
    if not (math.isfinite(flo) and math.isfinite(fhi)) or flo * fhi > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        fm = f(mid)
        if abs(fm) < 1e-9:
            return mid
        if flo * fm < 0:
            hi, fhi = mid, fm
        else:
            lo, flo = mid, fm
    return (lo + hi) / 2


def _on_or_after(index: pd.DatetimeIndex, ts: pd.Timestamp) -> pd.Timestamp | None:
    pos = index.searchsorted(ts, side="left")
    return index[pos] if pos < len(index) else None


def _month_starts(index: pd.DatetimeIndex, start: pd.Timestamp, end: pd.Timestamp, day: int = 1) -> list[pd.Timestamp]:
    out, cur = [], pd.Timestamp(year=start.year, month=start.month, day=1)
    while cur <= end:
        d = _on_or_after(index, cur + pd.Timedelta(days=day - 1))
        if d is not None and start <= d <= end:
            out.append(d)
        cur = cur + pd.DateOffset(months=1)
    return out


# --------------------------------------------------------------------------- historical
def lump_sum(nav: pd.Series, amount: float, start: pd.Timestamp, end: pd.Timestamp | None = None) -> dict:
    end = end or nav.index[-1]
    s, e = _on_or_after(nav.index, start), nav.loc[:end].index[-1]
    if s is None or s >= e:
        return {"available": False, "reason": "no NAV data in the chosen period"}
    units = amount / nav.loc[s]
    value = units * nav.loc[e]
    days = (e - s).days
    return {"kind": "historical", "available": True, "start": s.date().isoformat(), "end": e.date().isoformat(), "invested": amount,
            "final_value": float(value), "gain": float(value - amount), "cagr_pct": float(((value / amount) ** (365.25 / days) - 1) * 100) if days >= 30 else None}


def sip(nav: pd.Series, monthly: float, start: pd.Timestamp, end: pd.Timestamp | None = None, *, step_up_pct: float = 0.0,
        day: int = 1, inflation_pct: float | None = None) -> dict:
    """Invest `monthly` on the first NAV on/after `day` of each month. `step_up_pct` raises the amount every 12 months."""
    end = end or nav.index[-1]
    dates = _month_starts(nav.index, start, nav.loc[:end].index[-1], day)
    if len(dates) < 2:
        return {"available": False, "reason": "fewer than two instalments fit in the chosen period"}
    units, invested, flows, series = 0.0, 0.0, [], []
    for i, d in enumerate(dates):
        amt = monthly * (1 + step_up_pct / 100) ** (i // 12)
        units += amt / nav.loc[d]
        invested += amt
        flows.append((d.date(), -amt))
        series.append((d, units * nav.loc[d], invested))
    e = nav.loc[:end].index[-1]
    value = units * nav.loc[e]
    flows.append((e.date(), float(value)))
    r = xirr(flows)
    out = {"kind": "historical", "available": True, "start": dates[0].date().isoformat(), "end": e.date().isoformat(), "instalments": len(dates),
           "invested": float(invested), "final_value": float(value), "gain": float(value - invested), "xirr_pct": r * 100 if r is not None else None,
           "multiple": float(value / invested),
           "curve": [[d.date().isoformat(), round(float(v), 2), round(float(i), 2)] for d, v, i in series[:: max(1, len(series) // 300)]]}
    if inflation_pct is not None:
        infl = (1 + inflation_pct / 100) ** ((e - dates[0]).days / 365.25)
        out["final_value_real"] = float(value / infl)
        out["inflation_assumption_pct"] = inflation_pct
    return out


def swp(nav: pd.Series, corpus: float, monthly: float, start: pd.Timestamp, end: pd.Timestamp | None = None, *, inflation_pct: float = 0.0,
        day: int = 1) -> dict:
    """Invest `corpus` at `start`, then withdraw `monthly` (growing with `inflation_pct` a year) each month until `end` or depletion."""
    end = end or nav.index[-1]
    e = nav.loc[:end].index[-1]
    s = _on_or_after(nav.index, start)
    if s is None or s >= e:
        return {"available": False, "reason": "no NAV data in the chosen period"}
    units = corpus / nav.loc[s]
    dates = [d for d in _month_starts(nav.index, s, e, day) if d > s]
    withdrawn, depleted, flows, curve = 0.0, None, [(s.date(), -corpus)], []
    for i, d in enumerate(dates):
        want = monthly * (1 + inflation_pct / 100) ** (i / 12)
        need_units = want / nav.loc[d]
        if need_units >= units:
            got = units * nav.loc[d]
            withdrawn += got
            flows.append((d.date(), float(got)))
            units, depleted = 0.0, d
            curve.append((d, 0.0))
            break
        units -= need_units
        withdrawn += want
        flows.append((d.date(), float(want)))
        curve.append((d, units * nav.loc[d]))
    remaining = units * nav.loc[e] if depleted is None else 0.0
    if remaining > 0:
        flows.append((e.date(), float(remaining)))
    r = xirr(flows)
    return {"kind": "historical", "available": True, "start": s.date().isoformat(), "end": (depleted or e).date().isoformat(),
            "corpus": corpus, "total_withdrawn": float(withdrawn), "remaining_value": float(remaining),
            "depleted": depleted is not None, "depletion_date": depleted.date().isoformat() if depleted is not None else None,
            "months_paid": len(curve), "xirr_pct": r * 100 if r is not None else None,
            "curve": [[d.date().isoformat(), round(float(v), 2)] for d, v in curve[:: max(1, len(curve) // 300)]]}


def rolling_sip_outcomes(nav: pd.Series, monthly: float, horizon_years: float, step_months: int = 1) -> dict:
    """SIP result for every possible start month: how much does the outcome depend on when you began?"""
    first, last = nav.index[0], nav.index[-1]
    starts = _month_starts(nav.index, first, last - pd.DateOffset(months=round(horizon_years * 12)))[::step_months]
    rows = []
    for s in starts:
        e = s + pd.DateOffset(months=round(horizon_years * 12))
        r = sip(nav, monthly, s, e)
        if r.get("available") and r.get("xirr_pct") is not None:
            rows.append((s, r["xirr_pct"], r["multiple"]))
    if len(rows) < 12:
        return {"kind": "historical", "available": False, "reason": f"only {len(rows)} start dates have a full {horizon_years:g}-year history"}
    x = np.array([r[1] for r in rows])
    m = np.array([r[2] for r in rows])
    return {"kind": "historical", "available": True, "horizon_years": horizon_years, "start_dates": len(rows),
            "first_start": rows[0][0].date().isoformat(), "last_start": rows[-1][0].date().isoformat(),
            "xirr_pct": {p: float(np.percentile(x, q)) for p, q in (("p5", 5), ("p25", 25), ("median", 50), ("p75", 75), ("p95", 95))},
            "worst_xirr_pct": float(x.min()), "best_xirr_pct": float(x.max()), "share_losing_money": float((m < 1).mean() * 100),
            "multiple_median": float(np.median(m)),
            "series": [[s.date().isoformat(), round(float(v), 2)] for s, v, _ in rows[:: max(1, len(rows) // 250)]],
            "note": "Start dates overlap heavily, so these are not independent observations; the history is one path of one market."}


def rolling_swp_survival(nav: pd.Series, corpus: float, monthly: float, horizon_years: float, inflation_pct: float = 0.0, step_months: int = 1) -> dict:
    first, last = nav.index[0], nav.index[-1]
    starts = _month_starts(nav.index, first, last - pd.DateOffset(months=round(horizon_years * 12)))[::step_months]
    ok, rem, n = 0, [], 0
    for s in starts:
        r = swp(nav, corpus, monthly, s, s + pd.DateOffset(months=round(horizon_years * 12)), inflation_pct=inflation_pct)
        if not r.get("available"):
            continue
        n += 1
        ok += 0 if r["depleted"] else 1
        rem.append(r["remaining_value"])
    if n < 12:
        return {"kind": "historical", "available": False, "reason": f"only {n} start dates have a full {horizon_years:g}-year history"}
    return {"kind": "historical", "available": True, "horizon_years": horizon_years, "start_dates": n, "share_lasting_full_horizon": ok / n * 100,
            "remaining_value_percentiles": {p: float(np.percentile(rem, q)) for p, q in (("p5", 5), ("p25", 25), ("median", 50), ("p75", 75), ("p95", 95))},
            "note": "Overlapping start dates; one historical path."}


# --------------------------------------------------------------------------- hypothetical
def projection(monthly: float, years: float, annual_return_pct: float, annual_vol_pct: float, *, lump: float = 0.0, step_up_pct: float = 0.0,
               paths: int = 4000, seed: int = 0) -> dict:
    """HYPOTHETICAL: monthly instalments growing at an assumed return with assumed volatility (lognormal monthly returns)."""
    n = int(round(years * 12))
    rng = np.random.default_rng(seed)
    mu_m = math.log(1 + annual_return_pct / 100) / 12
    sd_m = annual_vol_pct / 100 / math.sqrt(12)
    z = rng.normal(0, 1, size=(paths, n))
    growth = np.exp(mu_m - 0.5 * sd_m**2 + sd_m * z)
    value = np.full(paths, float(lump))
    invested = lump
    for i in range(n):
        amt = monthly * (1 + step_up_pct / 100) ** (i // 12)
        value = (value + amt) * growth[:, i]
        invested += amt
    det = lump * (1 + annual_return_pct / 100) ** years
    for i in range(n):
        det += monthly * (1 + step_up_pct / 100) ** (i // 12) * (1 + annual_return_pct / 100) ** ((n - i) / 12)
    return {"kind": "hypothetical", "available": True, "years": years, "paths": paths, "invested": float(invested),
            "assumptions": {"annual_return_pct": annual_return_pct, "annual_volatility_pct": annual_vol_pct, "step_up_pct": step_up_pct, "lump_sum": lump},
            "deterministic_value": float(det), "percentiles": {p: float(np.percentile(value, q)) for p, q in (("p5", 5), ("p25", 25), ("median", 50), ("p75", 75), ("p95", 95))},
            "probability_below_invested_pct": float((value < invested).mean() * 100),
            "note": "An illustration under assumed return and volatility, not a forecast. Real returns are not lognormal and can differ materially."}


def bootstrap_projection(daily_returns: pd.Series, monthly: float, years: float, *, lump: float = 0.0, block: int = 21, paths: int = 3000, seed: int = 0) -> dict:
    """HYPOTHETICAL: resample blocks of this portfolio's own historical daily returns to build possible futures."""
    r = daily_returns.dropna().to_numpy()
    if len(r) < 500:
        return {"kind": "hypothetical", "available": False, "reason": "needs at least 500 daily observations to resample"}
    rng = np.random.default_rng(seed)
    n_months = int(round(years * 12))
    n_days = n_months * 21
    k = math.ceil(n_days / block)
    out = np.empty(paths)
    for p in range(paths):
        starts = rng.integers(0, len(r) - block, size=k)
        path = np.concatenate([r[s:s + block] for s in starts])[:n_days]
        grown = np.cumprod(1 + path)
        value = lump * grown[-1]
        for m in range(n_months):
            value += monthly * grown[-1] / grown[m * 21]
        out[p] = value
    invested = lump + monthly * n_months
    return {"kind": "hypothetical", "available": True, "years": years, "paths": paths, "invested": float(invested), "block_days": block,
            "percentiles": {p: float(np.percentile(out, q)) for p, q in (("p5", 5), ("p25", 25), ("median", 50), ("p75", 75), ("p95", 95))},
            "probability_below_invested_pct": float((out < invested).mean() * 100),
            "note": f"Resamples {block}-day blocks of {len(r)} historical daily returns. It can only recombine what happened, so it cannot show worse events than the history contains."}


# --------------------------------------------------------------------------- stress
def worst_episodes(index_series: pd.Series, n: int = 3, min_drawdown_pct: float = 5.0) -> list[dict]:
    """Deepest peak-to-trough episodes of a reference index, found from the data itself (no external event list).

    An episode runs from a running peak until the index regains that peak (or the data ends), so episodes cannot overlap."""
    s = index_series.dropna()
    if len(s) < 30:
        return []
    vals, idx = s.to_numpy(), s.index
    episodes, peak_i, trough_i = [], 0, 0
    for i in range(1, len(vals)):
        if vals[i] >= vals[peak_i]:
            if trough_i > peak_i and vals[trough_i] < vals[peak_i]:
                episodes.append((peak_i, trough_i))
            peak_i = trough_i = i
        elif vals[i] < vals[trough_i] or trough_i <= peak_i:
            trough_i = i
    if trough_i > peak_i and vals[trough_i] < vals[peak_i]:
        episodes.append((peak_i, trough_i))
    out = [{"peak": idx[p].date().isoformat(), "trough": idx[t].date().isoformat(), "fall_pct": float((vals[t] / vals[p] - 1) * 100),
            "days": int((idx[t] - idx[p]).days)} for p, t in episodes]
    out = [e for e in out if e["fall_pct"] <= -min_drawdown_pct]
    return sorted(out, key=lambda e: e["fall_pct"])[:n]


def window_return(nav: pd.Series, start: str, end: str) -> float | None:
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    a = nav.loc[:s]
    b = nav.loc[:e]
    if a.empty or b.empty or (s - a.index[-1]).days > 7 or nav.index[0] > s:
        return None
    return float((b.iloc[-1] / a.iloc[-1] - 1) * 100)


def beta_scenarios(portfolio_rets: pd.Series, market_rets: pd.Series, shocks_pct: list[float]) -> dict:
    """HYPOTHETICAL: portfolio change implied by market shocks through the historical beta (a linear approximation)."""
    idx = portfolio_rets.index.intersection(market_rets.index)
    if len(idx) < 250:
        return {"available": False, "reason": "fewer than 250 overlapping observations"}
    x, y = market_rets.loc[idx].to_numpy(), portfolio_rets.loc[idx].to_numpy()
    beta = float(np.cov(x, y, ddof=1)[0, 1] / x.var(ddof=1))
    return {"kind": "hypothetical", "available": True, "beta": beta, "r_squared": float(np.corrcoef(x, y)[0, 1] ** 2),
            "scenarios": [{"market_shock_pct": s, "portfolio_change_pct": beta * s} for s in shocks_pct],
            "note": "Linear and symmetric; real losses in a crisis are usually larger than beta implies because correlations rise."}


# --------------------------------------------------------------------------- rebalancing
def rebalance_plan(values: dict[str, float], targets: dict[str, float], *, new_cash: float = 0.0, threshold_pct: float = 5.0, min_trade: float = 0.0,
                   cost_pct: float = 0.0, held_days: dict[str, int] | None = None, exit_load_pct: float = 0.0, exit_load_days: int = 365,
                   buys_only: bool = False) -> dict:
    """Trades that bring holdings to target weights. `held_days` lets exit loads be charged on sells of recent purchases."""
    codes = sorted(set(values) | set(targets))
    tw = np.array([targets.get(c, 0.0) for c in codes], dtype=float)
    if abs(tw.sum() - 1) > 1e-6:
        raise ValueError("target weights must sum to 100%")
    cur = np.array([values.get(c, 0.0) for c in codes], dtype=float)
    total = cur.sum() + new_cash
    if total <= 0:
        raise ValueError("portfolio value must be positive")
    cw = cur / total
    drift = (cur / max(cur.sum(), 1e-12) - tw) * 100 if cur.sum() > 0 else -tw * 100
    breach = bool(np.abs(drift).max() >= threshold_pct)
    want = tw * total - cur
    if buys_only:
        # only add money: allocate new cash to the most underweight funds without selling
        want = np.where(want > 0, want, 0.0)
        s = want.sum()
        want = want * min(1.0, new_cash / s) if s > 0 else want
    trades, fees = [], 0.0
    for c, d, cv in zip(codes, want, cur):
        if abs(d) < max(min_trade, 1e-9):
            continue
        fee = cost_pct / 100 * abs(d)
        load = 0.0
        if d < 0 and held_days and held_days.get(c, 10**6) < exit_load_days:
            load = exit_load_pct / 100 * (-d)
        fees += fee + load
        trades.append({"code": c, "action": "buy" if d > 0 else "sell", "amount": float(abs(d)), "cost": float(fee), "exit_load": float(load)})
    return {"kind": "plan", "total_value": float(total), "threshold_pct": threshold_pct, "rebalance_triggered": breach,
            "max_drift_pct": float(np.abs(drift).max()), "estimated_fees": float(fees),
            "weights": [{"code": c, "current_pct": float(w * 100), "target_pct": float(t * 100), "drift_pct": float(dr)} for c, w, t, dr in zip(codes, cw, tw, drift)],
            "trades": sorted(trades, key=lambda t: -t["amount"]),
            "note": "Estimates only: fees, exit loads and tax depend on the scheme documents and your holding dates. Capital gains tax is not modelled."}
