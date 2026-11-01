"""Point-in-time backtesting of fund-selection strategies.

Honest by construction
- Signals at a rebalance date come from `history[date]`, which only uses NAV up to that date.
- Trades execute `delay_days` business days after the signal at that day's NAV (redemption and purchase are not
  instantaneous), and pay a transaction cost and an exit load on units held less than `exit_load_days`.
- The benchmark is the equal-weighted eligible universe on the same dates (zero cost): "did selection add value
  over simply holding everything comparable?"
- Known limits, repeated in every result's `warnings`: the universe is funds that exist today (survivorship bias);
  peer groups use today's classification; costs and loads are assumptions; taxes are not modelled; one historical
  path is one sample.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from quant_engine import scoring
from quant_engine.common import TRADING_DAYS

BACKTEST_VERSION = "backtest-1.0.0"
STRATEGIES = {
    "momentum_6m": "Top funds by 6-month return",
    "momentum_12m": "Top funds by 12-month return",
    "risk_adjusted_momentum": "Top funds by 12-month return divided by 1-year volatility",
    "consistency": "Top funds by the consistency factor (positive months, months beating peers)",
    "low_volatility": "Funds with the lowest 3-year volatility",
    "quality": "Top funds by risk-adjusted, consistency and downside factors combined",
    "multi_factor": "Top funds by the full QuantSynthica composite score",
    "regime_aware": "Composite score among risk-on funds in an uptrend, among defensive funds otherwise",
    "equal_weight": "Hold every eligible fund (naive baseline)",
}


@dataclass(frozen=True)
class BacktestConfig:
    strategy: str = "multi_factor"
    top_n: int = 10
    rebalance_months: int = 3
    start: str | None = None
    end: str | None = None
    cost_pct: float = 0.10
    exit_load_pct: float = 1.0
    exit_load_days: int = 365
    delay_days: int = 3
    oos_start: str | None = None
    min_funds: int = 5
    weights: tuple[tuple[str, float], ...] | None = None

    def hash(self, extra: str = "") -> str:
        return hashlib.sha256((json.dumps(asdict(self), sort_keys=True, default=str) + extra).encode()).hexdigest()[:16]


def select(strategy: str, df: pd.DataFrame, top_n: int) -> tuple[list[str], str | None]:
    """Choose funds from one date's score frame. Returns (codes, reason-if-none)."""
    if df.empty:
        return [], "no eligible funds"
    if strategy == "equal_weight":
        return list(df.index), None
    if strategy == "momentum_6m":
        key, asc = "mom_6m", False
    elif strategy == "momentum_12m":
        key, asc = "mom_12m", False
    elif strategy == "risk_adjusted_momentum":
        key, asc = "risk_adj_mom", False
    elif strategy == "low_volatility":
        key, asc = "vol_3y", True
    elif strategy == "consistency":
        key, asc = "f_consistency", False
    elif strategy in ("multi_factor", "regime_aware"):
        key, asc = "composite", False
    elif strategy == "quality":
        df = df.assign(_q=df[["f_risk_adjusted", "f_consistency", "f_downside"]].mean(axis=1, skipna=False))
        key, asc = "_q", False
    else:
        raise ValueError(f"unknown strategy '{strategy}'")
    ranked = df[key].dropna().sort_values(ascending=asc, kind="mergesort")  # stable: ties keep code order
    return list(ranked.index[:top_n]), None if len(ranked) else "no fund has the required metric"


def _curve_metrics(curve: pd.Series, rf: pd.Series | None) -> dict:
    curve = curve.dropna()
    if len(curve) < 60:
        return {"available": False, "reason": "fewer than 60 observations"}
    r = curve.pct_change().dropna()
    days = (curve.index[-1] - curve.index[0]).days
    cagr = ((curve.iloc[-1] / curve.iloc[0]) ** (365.25 / days) - 1) * 100 if days >= 30 else None
    vol = float(r.std(ddof=1) * math.sqrt(TRADING_DAYS) * 100)
    rfd = rf.reindex(r.index).ffill(limit=5).fillna(0) if rf is not None else pd.Series(0.0, index=r.index)
    ex = r - rfd
    sharpe = float(ex.mean() * TRADING_DAYS / (ex.std(ddof=1) * math.sqrt(TRADING_DAYS))) if ex.std(ddof=1) > 1e-12 and vol >= 0.5 else None
    dd = (curve / curve.cummax() - 1).min() * 100
    return {"available": True, "start": curve.index[0].date().isoformat(), "end": curve.index[-1].date().isoformat(),
            "cagr": cagr, "volatility": vol, "sharpe": sharpe, "max_drawdown": float(dd), "observations": len(r)}


def _monthly(curve: pd.Series) -> pd.Series:
    m = curve.groupby([curve.index.year, curve.index.month]).last()
    m.index = pd.PeriodIndex([pd.Period(year=y, month=mo, freq="M") for y, mo in m.index], freq="M")
    return m.pct_change().dropna()


def _bootstrap_ci(excess: np.ndarray, block: int = 3, n: int = 2000, seed: int = 0) -> tuple[float, float] | None:
    if len(excess) < 12:
        return None
    rng = np.random.default_rng(seed)
    k = math.ceil(len(excess) / block)
    means = []
    for _ in range(n):
        starts = rng.integers(0, len(excess) - block + 1, size=k)
        sample = np.concatenate([excess[s : s + block] for s in starts])[: len(excess)]
        means.append(sample.mean() * 12 * 100)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def _simulate(px: pd.DataFrame, events: list[tuple[pd.Timestamp, pd.Timestamp, list[str]]], cfg: BacktestConfig, costs: bool) -> dict:
    """Run the portfolio through the execution events. `events` = (signal date, execution date, target codes)."""
    units: dict[str, float] = {}
    bought: dict[str, pd.Timestamp] = {}
    value = 100.0
    curve_parts, trades, turnover = [], [], []
    total_cost = total_load = 0.0
    idx = px.index
    for k, (sig, ex, targets) in enumerate(events):
        pos = idx.get_loc(ex)
        end_pos = idx.get_loc(events[k + 1][1]) if k + 1 < len(events) else len(idx) - 1
        if units:
            held = list(units)
            cur_val = {c: units[c] * px.at[ex, c] for c in held}
            V = sum(v for v in cur_val.values() if not np.isnan(v))
        else:
            cur_val, V = {}, value
        targets = [c for c in targets if not np.isnan(px.at[ex, c])]
        if not targets:
            continue
        cost = load = 0.0
        tgt_value = V / len(targets)
        for _ in range(3):  # costs depend on trades which depend on costs: fixed-point iterate
            cost = load = traded = 0.0
            for c in set(cur_val) | set(targets):
                cur = cur_val.get(c, 0.0)
                tgt = tgt_value if c in targets else 0.0
                d = tgt - cur
                traded += abs(d)
                if costs:
                    cost += cfg.cost_pct / 100 * abs(d)
                    if d < 0 and c in bought and (ex - bought[c]).days < cfg.exit_load_days:
                        load += cfg.exit_load_pct / 100 * (-d)
            tgt_value = (V - cost - load) / len(targets)
        new_units: dict[str, float] = {}
        for c in targets:
            new_units[c] = tgt_value / px.at[ex, c]
            old = cur_val.get(c, 0.0)
            if old > 0 and c in bought:
                w = min(1.0, old / max(tgt_value, 1e-12))
                bought[c] = bought[c] + (ex - bought[c]) * (1 - w)  # added units are new; blend by value
            else:
                bought[c] = ex
        bought = {c: bought[c] for c in new_units}
        total_cost += cost
        total_load += load
        turnover.append(traded / 2 / V if V else 0.0)
        trades.append({"signal": sig.date().isoformat(), "execution": ex.date().isoformat(), "holdings": len(targets),
                       "turnover_pct": round(turnover[-1] * 100, 1), "cost_pct_of_value": round((cost + load) / V * 100, 3)})
        units = new_units
        seg = px.iloc[pos:end_pos + 1][list(units)]
        vals = seg.to_numpy() @ np.array([units[c] for c in seg.columns])
        curve_parts.append(pd.Series(vals, index=seg.index))
        value = float(vals[-1])
    if not curve_parts:
        return {"curve": pd.Series(dtype=float)}
    curve = pd.concat(curve_parts)
    curve = curve[~curve.index.duplicated(keep="first")]
    return {"curve": curve / curve.iloc[0] * 100, "trades": trades, "turnover": turnover, "cost": total_cost, "load": total_load}


def run_backtest(panel: pd.DataFrame, history: dict[pd.Timestamp, pd.DataFrame], universe: set[str], cfg: BacktestConfig,
                 rf: pd.Series | None = None, risk_on: pd.Series | None = None, defensive: set[str] | None = None) -> dict:
    if cfg.strategy not in STRATEGIES:
        raise ValueError(f"unknown strategy '{cfg.strategy}'")
    px = panel.ffill()  # a held fund that stops publishing keeps its last NAV
    dates = sorted(history)
    if cfg.start:
        dates = [d for d in dates if d >= pd.Timestamp(cfg.start)]
    if cfg.end:
        dates = [d for d in dates if d <= pd.Timestamp(cfg.end)]
    dates = dates[:: max(1, cfg.rebalance_months)]
    warnings = [
        "Survivorship bias: only funds that exist today are tested; funds that closed or merged are missing, which flatters every strategy.",
        "Peer groups use today's category classification at every historical date.",
        f"Costs are assumptions: {cfg.cost_pct}% of traded value, {cfg.exit_load_pct}% exit load on units held under {cfg.exit_load_days} days; taxes are not modelled.",
        "A single historical path is one sample; differences between strategies may be noise.",
    ]
    events, bench_events, skipped = [], [], 0
    for t in dates:
        df = history[t]
        df = df[df.index.isin(universe)]
        if cfg.strategy == "regime_aware":
            on = bool(risk_on.get(t, True)) if risk_on is not None else True
            pool = df if on else history[t][history[t].index.isin(defensive or set())]
        else:
            pool = df
        if cfg.strategy not in ("equal_weight", "momentum_6m", "momentum_12m", "risk_adjusted_momentum", "low_volatility"):
            elig = pool[pool.get("composite", pd.Series(dtype=float)).notna()] if "composite" in pool.columns else pool.iloc[0:0]
        else:
            elig = pool
        chosen, why = select(cfg.strategy, elig, cfg.top_n)
        eligible_all = list(df[df["ret_1y"].notna()].index) if "ret_1y" in df.columns else []
        pos = panel.index.searchsorted(t, side="right") - 1
        ex_pos = pos + cfg.delay_days
        if len(chosen) < min(cfg.min_funds, cfg.top_n) or ex_pos >= len(panel.index):
            skipped += 1
            continue
        ex = panel.index[ex_pos]
        events.append((t, ex, chosen))
        bench_events.append((t, ex, eligible_all))
    if len(events) < 3:
        return {"available": False, "reason": "fewer than 3 rebalances with enough eligible funds in this period", "warnings": warnings}
    if skipped:
        warnings.append(f"{skipped} rebalance date(s) skipped because too few funds were eligible.")

    strat = _simulate(px, events, cfg, costs=True)
    bench = _simulate(px, [e for e in bench_events if e[2]], cfg, costs=False)
    sc, bc = strat["curve"], bench["curve"]
    common = sc.index.intersection(bc.index)
    sc, bc = sc.loc[common], bc.loc[common]
    sc, bc = sc / sc.iloc[0] * 100, bc / bc.iloc[0] * 100

    sm, bm = _monthly(sc), _monthly(bc)
    both = pd.concat([sm, bm], axis=1, keys=["s", "b"]).dropna()
    excess = (both["s"] - both["b"]).to_numpy()
    t_stat = float(excess.mean() / (excess.std(ddof=1) / math.sqrt(len(excess)))) if len(excess) > 3 and excess.std(ddof=1) > 0 else None
    ci = _bootstrap_ci(excess)
    oos = pd.Timestamp(cfg.oos_start) if cfg.oos_start else sc.index[0] + (sc.index[-1] - sc.index[0]) * 0.6

    def seg(a, b):
        return {"strategy": _curve_metrics(sc.loc[a:b], rf), "benchmark": _curve_metrics(bc.loc[a:b], rf)}

    span_years = (sc.index[-1] - sc.index[0]).days / 365.25
    if span_years < 5:
        warnings.append(f"Only {span_years:.1f} years of history were testable: too short to separate skill from luck.")
    n_hold = float(np.mean([t["holdings"] for t in strat["trades"]]))
    full = {"strategy": _curve_metrics(sc, rf), "benchmark": _curve_metrics(bc, rf)}
    ex_cagr = (full["strategy"].get("cagr") or 0) - (full["benchmark"].get("cagr") or 0) if full["strategy"].get("available") else None
    step = max(1, len(sc) // 700)
    return {
        "available": True, "backtest_version": BACKTEST_VERSION, "scoring_version": scoring.SCORE_VERSION, "config": asdict(cfg),
        "strategy_description": STRATEGIES[cfg.strategy], "period": {"start": sc.index[0].date().isoformat(), "end": sc.index[-1].date().isoformat(), "years": round(span_years, 2)},
        "full": full, "in_sample": seg(sc.index[0], oos - pd.Timedelta(days=1)), "out_of_sample": seg(oos, sc.index[-1]), "oos_start": oos.date().isoformat(),
        "excess": {
            "cagr_difference_pp": ex_cagr, "months": len(excess), "monthly_excess_mean_pct": float(excess.mean() * 100),
            "t_stat": t_stat, "annualised_excess_ci95_pp": ci, "win_rate_pct": float((excess > 0).mean() * 100),
            "note": "t-statistic and bootstrap interval treat monthly excess returns as independent; both are rough with so few months.",
        },
        "costs": {"transaction_pct_of_start_value": round(strat["cost"] / 100 * 100, 2), "exit_loads_pct_of_start_value": round(strat["load"] / 100 * 100, 2),
                  "avg_annual_turnover_pct": round(float(np.mean(strat["turnover"])) * 12 / cfg.rebalance_months * 100, 1), "avg_holdings": round(n_hold, 1)},
        "trades": strat["trades"][-24:], "rebalances": len(events),
        "curves": {"strategy": [[d.date().isoformat(), round(float(v), 3)] for d, v in sc.iloc[::step].items()],
                   "benchmark": [[d.date().isoformat(), round(float(v), 3)] for d, v in bc.iloc[::step].items()]},
        "warnings": warnings,
    }
