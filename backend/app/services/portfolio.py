"""Portfolio analytics, optimisation, simulators, rebalancing and stress tests over the NAV universe.

Only Growth schemes with a confirmed NAV link (see `lite.universe`) can be used: IDCW NAVs exclude distributions.
Metric logic lives in quant_engine; this module validates requests, loads data and shapes results.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
from quant_engine import analysis
from quant_engine import portfolio as pf
from quant_engine import simulate as sm
from quant_engine.panel import daily_returns
from sqlalchemy.orm import Session

from app.services import lite

MAX_FUNDS = pf.MAX_FUNDS
METHODS = {
    "equal_weight": "Equal weight",
    "min_variance": "Minimum variance",
    "max_sharpe": "Maximum Sharpe (shrunk expected returns)",
    "risk_parity": "Risk parity (equal risk contribution)",
    "min_cvar": "Minimum CVaR (95%, historical scenarios)",
    "black_litterman": "Black-Litterman (needs your views)",
}


class RequestError(ValueError):
    pass


def _ids(session: Session, scheme_ids: list[int]) -> tuple[lite.Lite, list[str], pd.DataFrame]:
    if not scheme_ids:
        raise RequestError("select at least one fund")
    if len(set(scheme_ids)) != len(scheme_ids):
        raise RequestError("a fund appears more than once")
    if len(scheme_ids) > MAX_FUNDS:
        raise RequestError(f"at most {MAX_FUNDS} funds are supported")
    full = lite.universe(session)
    uni = full.reset_index().set_index("scheme_id")
    missing = [i for i in scheme_ids if i not in uni.index]
    if missing:
        raise RequestError(f"funds {missing} cannot be used: only Growth schemes with a confirmed link to official NAV records and a clean NAV history are supported")
    codes = [uni.at[i, "code"] for i in scheme_ids]
    b = lite.load(session, codes, full)
    gone = [i for i, c in zip(scheme_ids, codes) if c not in b.panel.columns]
    if gone:
        raise RequestError(f"funds {gone} cannot be used: their NAV history is missing, too short or contains an implausible jump")
    return b, codes, uni.loc[scheme_ids]


def _weights(holdings: list[dict]) -> tuple[list[int], np.ndarray]:
    if not holdings:
        raise RequestError("select at least one fund")
    ids = [int(h["scheme_id"]) for h in holdings]
    w = np.array([float(h["weight"]) for h in holdings], dtype=float)
    if (w < 0).any() or not np.isfinite(w).all():
        raise RequestError("weights must be zero or positive")
    if w.sum() <= 0:
        raise RequestError("weights must add up to more than zero")
    return ids, w / w.sum()


def _rf_annual(b: lite.Lite, window_days: int = 1096) -> float:
    if b.rf.empty:
        return 0.0
    r = b.rf.loc[b.rf.index > b.rf.index.max() - pd.Timedelta(days=window_days)]
    return float((1 + r.mean()) ** 252 - 1)


def _limits(req: dict, uni: pd.DataFrame) -> pf.Limits:
    lim = req.get("limits") or {}
    groups = []
    cat_max = lim.get("category_max_pct")
    if cat_max is not None:
        for cat, pos in uni.reset_index(drop=True).groupby("category").groups.items():
            groups.append((tuple(int(p) for p in pos), 0.0, float(cat_max) / 100))
    for tier, (lo, hi) in (lim.get("tier_limits") or {}).items():
        pos = [i for i, t in enumerate(uni["tier"]) if t == tier]
        if pos:
            groups.append((tuple(pos), float(lo) / 100, float(hi) / 100))
    return pf.Limits(float(lim.get("min_weight_pct", 0)) / 100, float(lim.get("max_weight_pct", 100)) / 100,
                     int(lim["max_funds"]) if lim.get("max_funds") else None, tuple(groups))


def _fund_rows(uni: pd.DataFrame, w: np.ndarray) -> list[dict]:
    return [{"scheme_id": int(sid), "name": r["name"], "category": r["category"], "plan": r["plan"], "tier": r["tier"], "weight_pct": float(x * 100)}
            for (sid, r), x in zip(uni.iterrows(), w)]


# ---------------------------------------------------------------------------- analyse
def analyze(session: Session, req: dict) -> dict[str, Any]:
    ids, w = _weights(req["holdings"])
    b, codes, uni = _ids(session, ids)
    rebalance = req.get("rebalance", "M")
    if rebalance not in ("M", "Q", "Y", "none"):
        raise RequestError("rebalance must be M, Q, Y or none")
    weights = dict(zip(codes, w))
    try:
        nav = pf.portfolio_nav(b.panel, weights, rebalance)
        bench = pf.portfolio_nav(b.panel, {c: 1 / len(codes) for c in codes}, rebalance)
    except pf.OptimisationError as exc:
        raise RequestError(str(exc)) from exc
    years = req.get("years", 3)
    years = None if years in ("max", None) else float(years)
    rf = b.rf if not b.rf.empty else None
    a = analysis.analyse(nav, bench, rf, rf_label="overnight/liquid fund median (proxy)", benchmark_label="Equal-weighted mix of the same funds")
    charts = analysis.chart_series(nav, bench, years)
    out: dict[str, Any] = {
        "version": pf.PORTFOLIO_VERSION, "funds": _fund_rows(uni, w), "rebalance": rebalance,
        "history": {"start": str(nav.index[0].date()), "end": str(nav.index[-1].date()), "observations": int(len(nav)),
                    "note": "History starts on the first date every selected fund has a NAV."},
        "analytics": a, "charts": charts,
        "allocation": {
            "by_category": _group(uni, w, "category"), "by_tier": _group(uni, w, "tier"), "by_plan": _group(uni, w, "plan"),
        },
        "warnings": [],
    }
    if len(codes) >= 2:
        rets = daily_returns(b.panel[codes]).dropna()
        rets = rets.loc[rets.index > rets.index.max() - pd.Timedelta(days=1096)]
        if len(rets) >= pf.MIN_OBS:
            est = pf.estimate(rets, 1096, 0.5)
            out["risk"] = {**pf.risk_decomposition(w, est.cov), "window": {"start": est.start, "end": est.end, "observations": est.n_obs},
                           "correlation": {"codes": [int(i) for i in ids], "matrix": np.round(rets.corr().to_numpy(), 3).tolist()},
                           "stats": pf.stats(w, est.mu_hist, est.cov, _rf_annual(b))}
            out["warnings"] += est.warnings
        else:
            out["warnings"].append("Fewer than 250 common daily observations in the last 3 years: risk decomposition and correlations are not shown.")
    return out


def _group(uni: pd.DataFrame, w: np.ndarray, col: str) -> list[dict]:
    s = pd.Series(w, index=uni[col].to_numpy()).groupby(level=0).sum().sort_values(ascending=False)
    return [{"name": k, "weight_pct": float(v * 100)} for k, v in s.items()]


# ---------------------------------------------------------------------------- optimise
def optimize(session: Session, req: dict) -> dict[str, Any]:
    method = req.get("method", "max_sharpe")
    if method not in METHODS:
        raise RequestError(f"method must be one of {sorted(METHODS)}")
    ids = [int(i) for i in req.get("scheme_ids", [])]
    if len(ids) < 2:
        raise RequestError("select at least two funds")
    b, codes, uni = _ids(session, ids)
    lookback = float(req.get("lookback_years", 3))
    shrink = float(req.get("shrink", 0.5))
    if not 1 <= lookback <= 10 or not 0 <= shrink <= 1:
        raise RequestError("lookback_years must be 1 to 10 and shrink 0 to 1")
    try:
        lim = _limits(req, uni)
        lim.check(len(codes))
    except pf.OptimisationError as exc:
        raise RequestError(str(exc)) from exc
    rets = daily_returns(b.panel[codes])
    rf = float(req["risk_free_pct"]) / 100 if req.get("risk_free_pct") is not None else _rf_annual(b, round(lookback * 365))
    try:
        est = pf.estimate(rets, round(lookback * 365), shrink)
    except pf.OptimisationError as exc:
        raise RequestError(str(exc)) from exc
    mu_used = est.mu
    notes: list[str] = []
    if method == "black_litterman":
        views = []
        pos = {i: k for k, i in enumerate(ids)}
        for v in req.get("views", []):
            if int(v["scheme_id"]) not in pos:
                raise RequestError("a view refers to a fund that is not selected")
            row = np.zeros(len(ids)); row[pos[int(v["scheme_id"])]] = 1.0
            views.append((row, float(v["annual_return_pct"]) / 100))
        if not views:
            raise RequestError("Black-Litterman needs at least one view (a fund and your expected annual return for it)")
        mu_used = pf.black_litterman(est.cov, np.full(len(ids), 1 / len(ids)), views)
        notes.append("Prior = equal-weight reverse optimisation (no reliable market-cap weights are available); your views move it.")

    def solve(e: pf.Estimates, l: pf.Limits) -> np.ndarray:
        if method == "equal_weight":
            return pf.equal_weight(len(e.codes), l)
        if method == "min_variance":
            return pf.min_variance(e.cov, l)
        if method == "risk_parity":
            return pf.risk_parity(e.cov, l)
        if method == "min_cvar":
            sc = rets[e.codes].loc[rets.index >= pd.Timestamp(e.start)].dropna().to_numpy()
            return pf.min_cvar(sc, l)[0]
        return pf.max_sharpe(mu_used if e is est else (e.mu), e.cov, rf, l)

    try:
        w = solve(est, lim)
        ew = np.full(len(codes), 1 / len(codes))
        out: dict[str, Any] = {
            "version": pf.PORTFOLIO_VERSION, "method": method, "method_label": METHODS[method], "funds": _fund_rows(uni, w),
            "stats": pf.stats(w, mu_used, est.cov, rf), "equal_weight_stats": pf.stats(ew, mu_used, est.cov, rf),
            "risk": pf.risk_decomposition(w, est.cov),
            "assumptions": {"lookback_years": lookback, "estimation_window": {"start": est.start, "end": est.end, "observations": est.n_obs},
                            "mean_return_shrinkage": shrink, "risk_free_pct": rf * 100, "covariance": "Ledoit-Wolf shrinkage",
                            "covariance_shrinkage_intensity": est.shrinkage_cov, "condition_number": est.condition_number,
                            "limits": req.get("limits") or {}},
            "warnings": list(est.warnings) + notes,
        }
        out["risk"]["risk_contribution_pct"] = out["risk"]["risk_contribution_pct"]
        if method != "min_cvar":
            fr = pf.efficient_frontier(mu_used, est.cov, lim, 25)
            out["frontier"] = [{"expected_return": p["expected_return"], "volatility": p["volatility"], "sharpe": p["sharpe"]} for p in fr]
        out["assets"] = [{"scheme_id": int(i), "name": uni.at[i, "name"], "expected_return": float(mu_used[k] * 100), "volatility": float(math.sqrt(est.cov[k, k]) * 100)}
                         for k, i in enumerate(ids)]
        if method == "min_cvar":
            cv = pf.min_cvar(rets[codes].loc[rets.index >= pd.Timestamp(est.start)].dropna().to_numpy(), lim)[1]
            out["daily_cvar_95_pct"] = cv * 100
        ho = pf.holdout_check(rets, lambda e, l: solve(e, l), lim, 365, round(lookback * 365), shrink, rf)
        out["holdout"] = ho
        if ho.get("available") and ho["optimised"]["return"] < ho["equal_weight"]["return"]:
            out["warnings"].append("On the most recent 12 months, held out of the fit, equal weight did better than this optimised portfolio. "
                                   "That is one sample, but optimisers often overfit estimated returns.")
        out["warnings"].append("Expected returns are shrunk historical averages, not forecasts. Optimised weights change materially with the window; treat them as one reasonable starting point.")
    except pf.OptimisationError as exc:
        raise RequestError(str(exc)) from exc
    if len(set(round(x, 4) for x in w if x > 1e-6)) == 1 and method != "equal_weight":
        out["warnings"].append("All weights came out identical: the constraints or the data left no room to differentiate funds.")
    return out


# ---------------------------------------------------------------------------- simulate
def _target_nav(session: Session, req: dict) -> tuple[pd.Series, dict, pd.Series | None]:
    t = req.get("target") or {}
    if "scheme_id" in t:
        b, codes, uni = _ids(session, [int(t["scheme_id"])])
        nav = b.panel[codes[0]].dropna()
        return nav, {"type": "fund", "name": uni.iloc[0]["name"]}, daily_returns(b.panel[[codes[0]]])[codes[0]].dropna()
    if t.get("holdings"):
        ids, w = _weights(t["holdings"])
        b, codes, uni = _ids(session, ids)
        try:
            nav = pf.portfolio_nav(b.panel, dict(zip(codes, w)), t.get("rebalance", "M"))
        except pf.OptimisationError as exc:
            raise RequestError(str(exc)) from exc
        return nav, {"type": "portfolio", "funds": len(ids)}, nav.pct_change().dropna()
    raise RequestError("target must be a fund ({scheme_id}) or a portfolio ({holdings})")


def _num(req: dict, key: str, lo: float, hi: float, default: float | None = None) -> float:
    v = req.get(key, default)
    if v is None:
        raise RequestError(f"{key} is required")
    v = float(v)
    if not lo <= v <= hi:
        raise RequestError(f"{key} must be between {lo:g} and {hi:g}")
    return v


def simulate(session: Session, req: dict) -> dict[str, Any]:
    kind = req.get("kind")
    nav, target, drets = _target_nav(session, req)
    first, last = nav.index[0], nav.index[-1]
    start = pd.Timestamp(req["start"]) if req.get("start") else first
    end = pd.Timestamp(req["end"]) if req.get("end") else last
    if start < first - pd.Timedelta(days=7) and req.get("start"):
        raise RequestError(f"start is before the data begins ({first.date()})")
    out: dict[str, Any]
    if kind == "sip":
        out = sm.sip(nav, _num(req, "monthly", 100, 1e8), start, end, step_up_pct=_num(req, "step_up_pct", 0, 50, 0), inflation_pct=req.get("inflation_pct"))
    elif kind == "lump_sum":
        out = sm.lump_sum(nav, _num(req, "amount", 100, 1e10), start, end)
    elif kind == "swp":
        out = sm.swp(nav, _num(req, "corpus", 1000, 1e10), _num(req, "monthly", 1, 1e8), start, end, inflation_pct=_num(req, "inflation_pct", 0, 20, 0))
    elif kind == "rolling_sip":
        out = sm.rolling_sip_outcomes(nav, _num(req, "monthly", 100, 1e8), _num(req, "horizon_years", 1, 20, 5))
    elif kind == "rolling_swp":
        out = sm.rolling_swp_survival(nav, _num(req, "corpus", 1000, 1e10), _num(req, "monthly", 1, 1e8), _num(req, "horizon_years", 1, 25, 10), _num(req, "inflation_pct", 0, 20, 0))
    elif kind == "projection":
        yrs = _num(req, "years", 1, 40, 10)
        hist_ret = float(((nav.iloc[-1] / nav.iloc[0]) ** (365.25 / (nav.index[-1] - nav.index[0]).days) - 1) * 100)
        hist_vol = float(drets.std(ddof=1) * math.sqrt(252) * 100)
        ret = _num(req, "annual_return_pct", -20, 40, min(max(hist_ret, -20), 40))
        vol = _num(req, "annual_volatility_pct", 0, 80, hist_vol)
        out = sm.projection(_num(req, "monthly", 0, 1e8, 0), yrs, ret, vol, lump=_num(req, "lump", 0, 1e10, 0), step_up_pct=_num(req, "step_up_pct", 0, 50, 0))
        out["history_for_reference"] = {"annualised_return_pct": hist_ret, "annualised_volatility_pct": hist_vol, "start": str(first.date()), "end": str(last.date())}
    elif kind == "bootstrap":
        out = sm.bootstrap_projection(drets, _num(req, "monthly", 0, 1e8, 0), _num(req, "years", 1, 30, 10), lump=_num(req, "lump", 0, 1e10, 0))
    else:
        raise RequestError("kind must be sip, lump_sum, swp, rolling_sip, rolling_swp, projection or bootstrap")
    return {"version": sm.SIM_VERSION, "target": target, "data": {"start": str(first.date()), "end": str(last.date())}, **out,
            "label": "Historical simulation: uses the actual NAV history" if out.get("kind") == "historical" else "Hypothetical projection: an illustration, not a forecast"}


# ---------------------------------------------------------------------------- rebalance
def rebalance(session: Session, req: dict) -> dict[str, Any]:
    holds = req.get("holdings") or []
    targets = req.get("targets") or []
    ids = sorted({int(h["scheme_id"]) for h in holds} | {int(t["scheme_id"]) for t in targets})
    b, codes, uni = _ids(session, ids)
    code_of = dict(zip(ids, codes))
    values = {code_of[int(h["scheme_id"])]: float(h["value"]) for h in holds}
    if any(v < 0 for v in values.values()):
        raise RequestError("holding values cannot be negative")
    tw = np.array([float(t["weight"]) for t in targets])
    if (tw < 0).any() or tw.sum() <= 0:
        raise RequestError("target weights must be positive")
    tw = tw / tw.sum()
    tgt = {code_of[int(t["scheme_id"])]: float(x) for t, x in zip(targets, tw)}
    held = {code_of[int(h["scheme_id"])]: int(h["held_days"]) for h in holds if h.get("held_days") is not None}
    try:
        plan = sm.rebalance_plan(values, tgt, new_cash=float(req.get("new_cash", 0)), threshold_pct=float(req.get("threshold_pct", 5)),
                                 min_trade=float(req.get("min_trade", 0)), cost_pct=float(req.get("cost_pct", 0)), held_days=held,
                                 exit_load_pct=float(req.get("exit_load_pct", 0)), exit_load_days=int(req.get("exit_load_days", 365)),
                                 buys_only=bool(req.get("buys_only", False)))
    except ValueError as exc:
        raise RequestError(str(exc)) from exc
    name = {code_of[i]: uni.at[i, "name"] for i in ids}
    sid = {v: k for k, v in code_of.items()}
    for row in plan["weights"] + plan["trades"]:
        row["name"] = name[row["code"]]
        row["scheme_id"] = sid[row["code"]]
        del row["code"]
    return {"version": sm.SIM_VERSION, **plan}


# ---------------------------------------------------------------------------- stress
def stress(session: Session, req: dict) -> dict[str, Any]:
    ids, w = _weights(req["holdings"])
    b, codes, uni = _ids(session, ids)
    mkt = lite.market_proxy(session)
    try:
        nav = pf.portfolio_nav(b.panel, dict(zip(codes, w)), "M")
    except pf.OptimisationError as exc:
        raise RequestError(str(exc)) from exc
    eps = sm.worst_episodes(mkt, int(req.get("episodes", 3)), 5.0)
    rows = []
    for e in eps:
        r = sm.window_return(nav, e["peak"], e["trough"])
        fund_r = {int(i): sm.window_return(b.panel[c].dropna(), e["peak"], e["trough"]) for i, c in zip(ids, codes)}
        rows.append({**e, "portfolio_change_pct": r, "available": r is not None,
                     "reason": None if r is not None else "the selected funds did not all exist at that time",
                     "funds": [{"scheme_id": i, "name": uni.at[i, "name"], "change_pct": fund_r[i]} for i in ids]})
    beta = sm.beta_scenarios(nav.pct_change().dropna(), mkt.pct_change().dropna(), [-10, -20, -30])
    return {"version": sm.SIM_VERSION, "market_proxy": "Equal-weighted Direct-plan equity funds that exist today (survivors only); episodes are found from this series, not from an external event list",
            "history": {"start": str(nav.index[0].date()), "end": str(nav.index[-1].date())}, "historical_episodes": rows, "hypothetical": beta,
            "notes": ["Historical episodes use what the selected funds actually did; funds launched later than an episode are reported as unavailable, not estimated.",
                      "The hypothetical table applies the portfolio's historical beta linearly and likely understates crisis losses."]}
