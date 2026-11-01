"""Factor research: point-in-time score history and predictive tests.

Survivorship and classification caveats apply to everything here: the universe is funds that exist today and peer
groups use today's category, so results describe survivors and are optimistic about persistence.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from quant_engine import scoring
from quant_engine.panel import last_on_or_before

MIN_INDEPENDENT = 10


def score_history(rets: pd.DataFrame, rf: pd.Series | None, groups: pd.Series, dates: list[pd.Timestamp],
                  weights: dict[str, float] | None = None) -> dict[pd.Timestamp, pd.DataFrame]:
    """Metrics and scores at each date, each using only returns up to that date."""
    out = {}
    for d in dates:
        m = scoring.factor_metrics(rets, rf, d, groups)
        sc = scoring.score_universe(m[scoring.METRIC_KEYS], groups, weights)
        out[d] = m.join(sc, how="left") if not sc.empty else m
    return out


def forward_relative(panel: pd.DataFrame, groups: pd.Series, date: pd.Timestamp, months: int) -> pd.Series:
    """Forward return over `months` minus the peer-group median forward return (peer-relative, in %)."""
    end = last_on_or_before(panel.index, date + pd.DateOffset(months=months))
    if end is None or end <= date or end > panel.index[-1] or (date + pd.DateOffset(months=months)) > panel.index[-1]:
        return pd.Series(dtype=float)
    a = panel.loc[date]
    b = panel.loc[end]
    fwd = (b / a - 1) * 100
    fwd = fwd[a.notna() & b.notna()]
    g = groups.reindex(fwd.index)
    return fwd - fwd.groupby(g).transform("median")


def _spearman(x: pd.Series, y: pd.Series) -> float | None:
    both = pd.concat([x, y], axis=1).dropna()
    if len(both) < 20 or both.iloc[:, 0].nunique() < 3:
        return None
    from scipy import stats

    return float(stats.spearmanr(both.iloc[:, 0], both.iloc[:, 1])[0])


def factor_ic(history: dict, panel: pd.DataFrame, groups: pd.Series, horizons: tuple[int, ...] = (1, 3, 6, 12),
              signals: list[str] | None = None) -> list[dict]:
    """Rank information coefficient of each signal against the peer-relative forward return.

    The t-statistic uses non-overlapping observations (every `h` months) because overlapping forward windows are
    strongly autocorrelated and would overstate significance.
    """
    dates = sorted(history)
    signals = signals or ["composite"] + [f"f_{f}" for f in scoring.FACTORS if f != "stability"] + [f"p_{k}" for k in scoring.METRIC_KEYS]
    rows = []
    for h in horizons:
        fwd = {d: forward_relative(panel, groups, d, h) for d in dates}
        fwd = {d: s for d, s in fwd.items() if len(s) >= 20}
        for sig in signals:
            ics, spreads = {}, {}
            for d, f in fwd.items():
                df = history[d]
                if sig not in df.columns:
                    continue
                x = df[sig]
                ic = _spearman(x.reindex(f.index), f)
                if ic is not None:
                    ics[d] = ic
                top = f[x.reindex(f.index) >= 80]
                bot = f[x.reindex(f.index) <= 20]
                if len(top) >= 5 and len(bot) >= 5:
                    spreads[d] = float(top.mean() - bot.mean())
            if len(ics) < 6:
                continue
            s = pd.Series(ics).sort_index()
            non = s.iloc[:: max(1, h)]
            # fewer than MIN_INDEPENDENT non-overlapping dates: a t-statistic would be meaningless, so none is reported
            t = float(non.mean() / (non.std(ddof=1) / math.sqrt(len(non)))) if len(non) >= MIN_INDEPENDENT and non.std(ddof=1) > 0 else None
            sp = pd.Series(spreads).sort_index()
            rows.append({
                "signal": sig, "horizon_months": h, "mean_ic": float(s.mean()), "ic_std": float(s.std(ddof=1)),
                "hit_rate": float((s > 0).mean()), "dates": len(s), "independent_dates": len(non), "t_stat": t,
                "top_minus_bottom_pct": float(sp.mean()) if len(sp) else None,
                "avg_funds": float(np.mean([len(fwd[d]) for d in s.index])),
                "first_date": s.index[0].date().isoformat(), "last_date": s.index[-1].date().isoformat(),
            })
    return rows


def factor_correlations(history: dict, keys: list[str]) -> dict:
    """Average cross-sectional rank correlation between factor scores across dates."""
    mats = []
    for df in history.values():
        sub = df[[k for k in keys if k in df.columns]].dropna(how="all")
        if len(sub) >= 30:
            mats.append(sub.rank().corr().reindex(index=keys, columns=keys))
    if not mats:
        return {"keys": keys, "matrix": []}
    m = pd.concat(mats).groupby(level=0).mean().reindex(index=keys, columns=keys)
    return {"keys": keys, "matrix": m.round(3).fillna(0).to_numpy().tolist(), "dates": len(mats)}


def distribution_summary(df: pd.DataFrame, keys: list[str]) -> list[dict]:
    from scipy import stats

    out = []
    for k in keys:
        s = df[k].dropna() if k in df.columns else pd.Series(dtype=float)
        if len(s) < 20:
            continue
        out.append({"metric": k, "n": len(s), "mean": float(s.mean()), "std": float(s.std(ddof=1)),
                    "p5": float(s.quantile(.05)), "median": float(s.median()), "p95": float(s.quantile(.95)),
                    "skew": float(stats.skew(s)), "excess_kurtosis": float(stats.kurtosis(s))})
    return out


def persistence(history: dict, panel: pd.DataFrame, groups: pd.Series, months: int = 12) -> dict:
    """Do funds in the top quartile of the composite score at t land in the top quartile of peer-relative return
    over the NEXT `months`? Using subsequent returns avoids the mechanical overlap between trailing-window scores
    (a 3-year score 12 months later shares two thirds of its data), which would show "persistence" even in noise."""
    stay, total = 0, 0
    for d in sorted(history):
        comp = history[d].get("composite")
        if comp is None:
            continue
        fwd = forward_relative(panel, groups, d, months)
        if len(fwd) < 20:
            continue
        g = groups.reindex(fwd.index)
        fwd_rank = fwd.groupby(g).rank(pct=True)
        c = comp.reindex(fwd.index)
        top = c[c >= c.groupby(g).transform(lambda x: x.quantile(0.75))].dropna().index
        hit = fwd_rank.reindex(top).dropna()
        if len(hit) >= 5:
            stay += int((hit > 0.75).sum())
            total += len(hit)
    return {"months": months, "observations": total, "share_in_top_quartile_next": stay / total if total else None,
            "random_expectation": 0.25,
            "note": "Overlapping dates make observations dependent; treat as descriptive, not a significance test."}
