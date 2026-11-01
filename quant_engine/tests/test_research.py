import numpy as np
import pandas as pd
from quant_engine.panel import month_ends
from tests.synth import make_panel, rf_series

from quant_engine import research


def build(drift_sd, n=40, years=9, seed=2):
    panel, rets, groups = make_panel(n_funds=n, years=years, seed=seed, groups=2, vol=0.006,
                                     drift=np.random.default_rng(seed).normal(0, drift_sd, n))
    dates = month_ends(rets.index, rets.index[0] + pd.DateOffset(years=3, months=1), rets.index[-1] - pd.DateOffset(months=13), 1)
    hist = research.score_history(rets, rf_series(rets.index), groups, dates)
    return panel, groups, hist


def test_a_planted_persistent_edge_is_detected():
    panel, groups, hist = build(drift_sd=0.0004)  # large, persistent differences in fund drift
    rows = {(r["signal"], r["horizon_months"]): r for r in research.factor_ic(hist, panel, groups, horizons=(3, 12), signals=["composite", "p_ret_3y"])}
    r = rows[("p_ret_3y", 3)]
    assert r["mean_ic"] > 0.15 and r["t_stat"] > 3 and r["top_minus_bottom_pct"] > 0
    assert r["independent_dates"] < r["dates"]  # the t-stat uses non-overlapping observations only
    assert rows[("p_ret_3y", 12)]["t_stat"] is None  # only a handful of non-overlapping 12-month windows: no t-stat


def test_no_edge_gives_no_significant_signal():
    panel, groups, hist = build(drift_sd=0.0)  # identical expected returns: past performance cannot predict
    rows = research.factor_ic(hist, panel, groups, horizons=(12,), signals=["composite", "p_ret_3y", "p_mom_12m"])
    assert rows and all(abs(r["mean_ic"]) < 0.15 for r in rows)
    assert all(abs(r["t_stat"]) < 3 for r in rows if r["t_stat"] is not None)


def test_forward_returns_are_peer_relative_and_only_defined_with_a_full_horizon():
    panel, rets, groups = make_panel(n_funds=12, years=4, seed=3)
    d = rets.index[300]
    f = research.forward_relative(panel, groups, d, 6)
    assert abs(f.groupby(groups.reindex(f.index)).median()).max() < 1e-9  # demeaned within group
    assert research.forward_relative(panel, groups, rets.index[-30], 6).empty  # horizon runs past the data


def test_distribution_and_correlation_helpers():
    panel, groups, hist = build(drift_sd=0.0002, n=30, years=8)
    last = hist[max(hist)]
    dist = research.distribution_summary(last, ["sharpe_3y", "ret_3y"])
    assert {d["metric"] for d in dist} == {"sharpe_3y", "ret_3y"} and all(d["p5"] < d["median"] < d["p95"] for d in dist)
    corr = research.factor_correlations(hist, ["f_performance", "f_risk_adjusted", "f_momentum"])
    m = np.array(corr["matrix"])
    assert np.allclose(np.diag(m), 1.0) and np.allclose(m, m.T)


def test_persistence_is_above_chance_only_when_edges_exist():
    p1, g1, with_edge = build(drift_sd=0.0004, seed=4)
    p2, g2, no_edge = build(drift_sd=0.0, seed=4)
    a, b = research.persistence(with_edge, p1, g1, 12), research.persistence(no_edge, p2, g2, 12)
    assert a["share_in_top_quartile_next"] > 0.4
    assert b["share_in_top_quartile_next"] < 0.35 and b["random_expectation"] == 0.25  # noise alone stays near 25%


def test_t_statistic_is_withheld_with_too_few_independent_dates():
    panel, groups, hist = build(drift_sd=0.0004, n=30, years=7)
    rows = research.factor_ic({d: hist[d] for d in sorted(hist)[:8]}, panel, groups, horizons=(1,), signals=["composite"])
    assert rows and rows[0]["independent_dates"] < research.MIN_INDEPENDENT and rows[0]["t_stat"] is None
