"""QuantSynthica Fund Score (methodology score-1.0.0): point-in-time factor metrics and a peer-relative composite.

Everything here is a function of NAV information available on or before `asof`. Nothing after `asof` is read.

Factors and initial weights are research hypotheses, not validated optima:
  Performance 25, Risk-adjusted 25, Consistency 20, Downside protection 15, Momentum 10, Stability 5.
Stability (AUM, expense and manager history) cannot be computed from NAV, so it is reported as unavailable and the
other weights are renormalised per fund (coverage-aware). Missing metrics are never filled with zero.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from quant_engine.common import TRADING_DAYS

SCORE_VERSION = "score-1.0.0"
MIN_PEERS = 5
MIN_COVERAGE = 0.6  # of the full 100% weight; Stability alone makes 0.95 the maximum reachable
MIN_WINDOW_FILL = 0.9  # share of expected business days a fund must have in a window for its metrics
WINSOR = (0.05, 0.95)

WEIGHTS = {"performance": 25.0, "risk_adjusted": 25.0, "consistency": 20.0, "downside": 15.0, "momentum": 10.0, "stability": 5.0}


@dataclass(frozen=True)
class MetricDef:
    key: str
    factor: str
    higher_is_better: bool
    label: str


METRICS: list[MetricDef] = [
    MetricDef("ret_1y", "performance", True, "1Y return"),
    MetricDef("ret_3y", "performance", True, "3Y return (p.a.)"),
    MetricDef("ret_5y", "performance", True, "5Y return (p.a.)"),
    MetricDef("sharpe_3y", "risk_adjusted", True, "3Y Sharpe"),
    MetricDef("sortino_3y", "risk_adjusted", True, "3Y Sortino"),
    MetricDef("calmar_3y", "risk_adjusted", True, "3Y Calmar"),
    MetricDef("info_ratio_3y", "risk_adjusted", True, "3Y information ratio (vs peers)"),
    MetricDef("pos_months_3y", "consistency", True, "Positive months (3Y)"),
    MetricDef("beat_peers_months_3y", "consistency", True, "Months beating peer median (3Y)"),
    MetricDef("max_dd_3y", "downside", True, "3Y max drawdown"),  # less negative = better
    MetricDef("downside_dev_3y", "downside", False, "3Y downside deviation"),
    MetricDef("downside_capture_3y", "downside", False, "Downside capture (3Y, vs peers)"),
    MetricDef("mom_3m", "momentum", True, "3M momentum"),
    MetricDef("mom_6m", "momentum", True, "6M momentum"),
    MetricDef("mom_12m", "momentum", True, "12M momentum"),
    MetricDef("risk_adj_mom", "momentum", True, "12M momentum / 1Y volatility"),
]
METRIC_KEYS = [m.key for m in METRICS]
EXTRA_KEYS = ["vol_3y"]  # computed for strategies and clustering, not part of the score
FACTORS = list(WEIGHTS)


def _window(rets: pd.DataFrame, asof: pd.Timestamp, days: int) -> pd.DataFrame:
    return rets.loc[(rets.index > asof - pd.Timedelta(days=days)) & (rets.index <= asof)]


def _enough(w: pd.DataFrame, days: int) -> pd.Series:
    expected = days * TRADING_DAYS / 365.25
    return w.notna().sum() >= MIN_WINDOW_FILL * expected


def _compound(w: pd.DataFrame) -> pd.Series:
    return (1 + w.fillna(0)).prod() - 1


def _month_panel(w: pd.DataFrame) -> pd.DataFrame:
    g = w.groupby([w.index.year, w.index.month])
    return g.apply(lambda x: (1 + x.fillna(0)).prod() - 1).where(g.count() > 0)


def factor_metrics(rets: pd.DataFrame, rf: pd.Series | None, asof: pd.Timestamp, groups: pd.Series) -> pd.DataFrame:
    """Raw metrics per fund at `asof`. `rets` are daily returns (dates x codes); `groups` maps code -> peer group."""
    r = rets.loc[:asof]
    rfd = (rf.reindex(r.index).ffill(limit=5) if rf is not None else pd.Series(0.0, index=r.index)).fillna(0.0)
    out = pd.DataFrame(index=r.columns, columns=METRIC_KEYS + EXTRA_KEYS, dtype=float)

    w1, w3, w5 = _window(r, asof, 365), _window(r, asof, 365 * 3 + 1), _window(r, asof, 365 * 5 + 2)
    ok1, ok3, ok5 = _enough(w1, 365), _enough(w3, 365 * 3), _enough(w5, 365 * 5)

    out.loc[ok1, "ret_1y"] = _compound(w1)[ok1] * 100
    out.loc[ok3, "ret_3y"] = (((1 + _compound(w3)[ok3]).clip(lower=1e-9)) ** (1 / 3) - 1) * 100
    out.loc[ok5, "ret_5y"] = (((1 + _compound(w5)[ok5]).clip(lower=1e-9)) ** (1 / 5) - 1) * 100

    # ---- risk-adjusted (3Y window, daily)
    ex = w3.sub(rfd.reindex(w3.index).values, axis=0)
    sd = ex.std(ddof=1)
    mean = ex.mean()
    valid = ok3 & (sd * math.sqrt(TRADING_DAYS) * 100 >= 0.5)  # ratios withheld for money-market-like volatility
    out.loc[valid, "sharpe_3y"] = (mean * TRADING_DAYS / (sd * math.sqrt(TRADING_DAYS)))[valid]
    dd = np.sqrt((ex.clip(upper=0) ** 2).mean()) * math.sqrt(TRADING_DAYS)
    vs = ok3 & (dd > 1e-9) & (sd * math.sqrt(TRADING_DAYS) * 100 >= 0.5)
    out.loc[vs, "sortino_3y"] = (mean * TRADING_DAYS / dd)[vs]
    out.loc[ok3, "vol_3y"] = (w3.std(ddof=1) * math.sqrt(TRADING_DAYS) * 100)[ok3]
    out.loc[ok3, "downside_dev_3y"] = (np.sqrt((w3.clip(upper=0) ** 2).mean()) * math.sqrt(TRADING_DAYS) * 100)[ok3]

    cum = (1 + w3.fillna(0)).cumprod()
    maxdd = (cum / cum.cummax() - 1).min() * 100
    out.loc[ok3, "max_dd_3y"] = maxdd[ok3]
    cal = out["ret_3y"] / maxdd.abs().where(maxdd < -0.05)
    out.loc[ok3, "calmar_3y"] = cal[ok3]

    # ---- peer-relative (information ratio, months beating peers, downside capture), vectorised per peer group
    grp = groups.reindex(w3.columns)
    peer_mean = pd.DataFrame(np.nan, index=w3.index, columns=w3.columns)
    m = _month_panel(w3).astype(float)
    med = pd.DataFrame(np.nan, index=m.index, columns=m.columns)
    for g, cols in grp.groupby(grp).groups.items():
        cols = list(cols)
        if len(cols) < MIN_PEERS:
            continue
        arr = w3[cols].to_numpy()
        mask = ~np.isnan(arr)
        tot = np.where(mask, arr, 0.0).sum(axis=1)
        n = mask.sum(axis=1)
        cnt = n[:, None] - mask  # peers other than the fund itself
        with np.errstate(invalid="ignore", divide="ignore"):
            pm = (tot[:, None] - np.where(mask, arr, 0.0)) / cnt
        pm[cnt < MIN_PEERS - 1] = np.nan
        peer_mean[cols] = pm
        med[cols] = np.repeat(m[cols].median(axis=1).to_numpy()[:, None], len(cols), axis=1)
    active = w3 - peer_mean
    te = active.std(ddof=1)
    vi = ok3 & (te * math.sqrt(TRADING_DAYS) * 100 >= 0.25)
    out.loc[vi, "info_ratio_3y"] = (active.mean() * TRADING_DAYS / (te * math.sqrt(TRADING_DAYS)))[vi]

    mp = _month_panel(peer_mean.where(w3.notna()))  # peer average over the days the fund exists
    full_months = m.notna().sum() >= 30
    out.loc[full_months, "pos_months_3y"] = ((m > 0).sum() / m.notna().sum() * 100)[full_months]
    both = m.notna() & med.notna()
    beat = ((m > med) & both).sum()
    out.loc[full_months, "beat_peers_months_3y"] = (beat / both.sum().replace(0, np.nan) * 100)[full_months]
    down = (mp < 0) & m.notna()
    n_down = down.sum()
    with np.errstate(invalid="ignore", divide="ignore"):
        dc = (m.where(down).sum() / n_down) / (mp.where(down).sum() / n_down) * 100
    okdc = full_months & (n_down >= 6) & (mp.where(down).mean() < 0)
    out.loc[okdc, "downside_capture_3y"] = dc[okdc]

    # ---- momentum
    for key, days in (("mom_3m", 91), ("mom_6m", 182), ("mom_12m", 365)):
        w = _window(r, asof, days)
        ok = _enough(w, days)
        out.loc[ok, key] = _compound(w)[ok] * 100
    vol1 = w1.std(ddof=1) * math.sqrt(TRADING_DAYS) * 100
    okv = ok1 & (vol1 > 0.5)
    out.loc[okv, "risk_adj_mom"] = (out["mom_12m"] / vol1)[okv]
    return out


# ---------------------------------------------------------------- normalisation & composite
def _winsorise(s: pd.Series) -> pd.Series:
    lo, hi = s.quantile(WINSOR[0]), s.quantile(WINSOR[1])
    return s.clip(lo, hi)


def score_group(metrics: pd.DataFrame, weights: dict[str, float] | None = None) -> dict[str, pd.DataFrame]:
    """Within one peer group: percentiles (0-100, higher = better), z-scores, factor scores, composite, coverage."""
    w = {k: (weights or WEIGHTS).get(k, 0.0) for k in FACTORS}
    pct = pd.DataFrame(index=metrics.index, columns=METRIC_KEYS, dtype=float)
    z = pct.copy()
    for md in METRICS:
        col = metrics[md.key].dropna()
        if len(col) < MIN_PEERS:
            continue
        wz = _winsorise(col)
        rank = wz.rank(method="average", ascending=md.higher_is_better) - 1
        pct.loc[col.index, md.key] = rank / (len(col) - 1) * 100
        sdv = wz.std(ddof=1)
        zz = (wz - wz.mean()) / sdv if sdv and sdv > 1e-12 else wz * 0
        z.loc[col.index, md.key] = zz if md.higher_is_better else -zz
    factors = pd.DataFrame(index=metrics.index, columns=FACTORS, dtype=float)
    for f in FACTORS:
        keys = [m.key for m in METRICS if m.factor == f]
        if keys:
            factors[f] = pct[keys].mean(axis=1, skipna=True).where(pct[keys].notna().any(axis=1))
    total = sum(w.values())
    avail_w = factors.notna().mul(pd.Series(w)).sum(axis=1)
    coverage = avail_w / total if total else avail_w
    renorm = factors.notna().mul(pd.Series(w)).div(avail_w.replace(0, np.nan), axis=0)
    contrib = factors.fillna(0) * renorm
    composite = contrib.sum(axis=1).where((coverage >= MIN_COVERAGE) & (avail_w > 0))
    return {"pct": pct, "z": z, "factors": factors, "contrib": contrib, "composite": composite.to_frame("composite"),
            "coverage": coverage.to_frame("coverage")}


def score_universe(metrics: pd.DataFrame, groups: pd.Series, weights: dict[str, float] | None = None) -> pd.DataFrame:
    """Composite score for every fund, computed within its own peer group. Groups below MIN_PEERS stay unscored."""
    parts = []
    for g, cols in groups.reindex(metrics.index).groupby(groups.reindex(metrics.index)).groups.items():
        sub = metrics.loc[list(cols)]
        if sub.notna().any(axis=1).sum() < MIN_PEERS:
            continue
        res = score_group(sub, weights)
        d = pd.concat([res["composite"], res["coverage"], res["factors"].add_prefix("f_"), res["contrib"].add_prefix("c_"),
                       res["pct"].add_prefix("p_"), res["z"].add_prefix("z_")], axis=1)
        d["group"] = g
        d["peers"] = len(sub)
        d["rank"] = d["composite"].rank(ascending=False, method="min")
        parts.append(d)
    return pd.concat(parts) if parts else pd.DataFrame()
