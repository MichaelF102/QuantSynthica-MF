import numpy as np
import pandas as pd
import pytest
from quant_engine.panel import month_ends
from tests.synth import make_panel, rf_series

from quant_engine import backtest as bt
from quant_engine import research


@pytest.fixture(scope="module")
def world():
    drift = np.random.default_rng(7).normal(0, 0.0004, 24)  # persistent differences between funds
    panel, rets, groups = make_panel(n_funds=24, years=11, seed=7, groups=1, vol=0.006, drift=drift)
    dates = month_ends(rets.index, rets.index[0] + pd.DateOffset(years=3, months=1), rets.index[-1] - pd.DateOffset(months=1), 1)
    hist = research.score_history(rets, rf_series(rets.index), groups, dates)
    return panel, rets, groups, hist, set(panel.columns)


def run(world, **kw):
    panel, rets, groups, hist, universe = world
    return bt.run_backtest(panel, hist, universe, bt.BacktestConfig(**kw), rf_series(panel.index))


def test_result_carries_provenance_split_costs_and_warnings(world):
    r = run(world, strategy="multi_factor", top_n=6, rebalance_months=3)
    assert r["available"] and r["backtest_version"] == bt.BACKTEST_VERSION and r["scoring_version"] == "score-1.0.0"
    assert r["in_sample"]["strategy"]["available"] and r["out_of_sample"]["strategy"]["available"]
    assert r["costs"]["avg_holdings"] == pytest.approx(6.0)
    assert any("Survivorship" in w for w in r["warnings"]) and any("assumptions" in w for w in r["warnings"])
    assert r["excess"]["annualised_excess_ci95_pp"] is not None and r["curves"]["strategy"][0][1] == 100.0


def test_selection_on_a_persistent_edge_beats_the_equal_weight_benchmark_before_costs(world):
    r = run(world, strategy="momentum_12m", top_n=5, rebalance_months=3, cost_pct=0.0, exit_load_pct=0.0)
    assert r["excess"]["cagr_difference_pp"] > 0 and r["excess"]["t_stat"] > 1


def test_costs_and_exit_loads_reduce_returns(world):
    free = run(world, strategy="momentum_12m", top_n=5, rebalance_months=1, cost_pct=0.0, exit_load_pct=0.0)
    paid = run(world, strategy="momentum_12m", top_n=5, rebalance_months=1, cost_pct=0.5, exit_load_pct=1.0)
    assert paid["full"]["strategy"]["cagr"] < free["full"]["strategy"]["cagr"]
    assert paid["costs"]["transaction_pct_of_start_value"] > 0
    assert paid["full"]["benchmark"]["cagr"] == pytest.approx(free["full"]["benchmark"]["cagr"])  # the benchmark never pays costs


def test_results_are_reproducible_and_the_config_hash_changes_with_the_config(world):
    a, b = run(world, strategy="quality", top_n=5), run(world, strategy="quality", top_n=5)
    assert a["curves"] == b["curves"] and a["full"] == b["full"]
    assert bt.BacktestConfig(top_n=5).hash() == bt.BacktestConfig(top_n=5).hash() != bt.BacktestConfig(top_n=6).hash()


def test_no_look_ahead_future_data_cannot_change_past_trades(world):
    panel, rets, groups, hist, universe = world
    cut = sorted(hist)[len(hist) // 2]
    cfg = bt.BacktestConfig(strategy="multi_factor", top_n=5, rebalance_months=3, end=str(cut.date()))
    base = bt.run_backtest(panel, {d: v for d, v in hist.items() if d <= cut}, universe, cfg, rf_series(panel.index))
    # same run on a panel whose NAVs after the cut are replaced by garbage
    mutated = panel.copy()
    mutated.loc[mutated.index > cut] = np.random.default_rng(1).uniform(1, 1000, mutated.loc[mutated.index > cut].shape)
    hist2 = research.score_history(mutated.pct_change(fill_method=None), rf_series(panel.index), groups,
                                   [d for d in sorted(hist) if d <= cut])
    again = bt.run_backtest(mutated, hist2, universe, cfg, rf_series(panel.index))
    assert [t["signal"] for t in base["trades"]] == [t["signal"] for t in again["trades"]]
    assert [t["holdings"] for t in base["trades"]] == [t["holdings"] for t in again["trades"]]
    pre = pd.Timestamp(base["trades"][-1]["execution"])  # after the last trade the curve is just valuation at later prices
    b = pd.Series(dict(base["curves"]["strategy"]))
    a = pd.Series(dict(again["curves"]["strategy"]))
    common = [d for d in b.index if d in a.index and pd.Timestamp(d) <= pre]
    assert len(common) > 50 and np.allclose(b.loc[common].astype(float), a.loc[common].astype(float))


def test_execution_is_delayed_by_the_configured_business_days(world):
    r = run(world, strategy="multi_factor", top_n=5, delay_days=5)
    for t in r["trades"]:
        gap = np.busday_count(t["signal"], t["execution"])
        assert gap == 5


def test_toy_cost_accounting_matches_a_hand_calculation():
    idx = pd.bdate_range("2020-01-01", periods=60)
    px = pd.DataFrame({"A": 100 * 1.001 ** np.arange(60), "B": 100 * 1.002 ** np.arange(60)}, index=idx)
    cfg = bt.BacktestConfig(strategy="equal_weight", cost_pct=1.0, exit_load_pct=2.0, exit_load_days=365, delay_days=0)
    # first event: buy A and B from nothing (traded = 100, cost 1% = 1.0); second event: sell all of A for B (exit load applies)
    events = [(idx[0], idx[0], ["A", "B"]), (idx[20], idx[20], ["B"])]
    sim = bt._simulate(px, events, cfg, costs=True)
    # event 1: buy A and B from nothing
    V0 = 100.0
    tgt = V0 / 2
    for _ in range(3):
        cost1 = 0.01 * (2 * tgt)
        tgt = (V0 - cost1) / 2
    tgt1 = tgt
    ua, ub = tgt / px.at[idx[0], "A"], tgt / px.at[idx[0], "B"]
    # event 2: sell all of A (held 20 days: exit load applies), keep B as the only holding
    a_val, b_val = ua * px.at[idx[20], "A"], ub * px.at[idx[20], "B"]
    V = a_val + b_val
    tgt = V
    for _ in range(3):
        traded = a_val + abs(tgt - b_val)
        cost2 = 0.01 * traded
        load = 0.02 * a_val
        tgt = V - cost2 - load
    assert sim["cost"] == pytest.approx(cost1 + cost2, rel=1e-9) and sim["load"] == pytest.approx(load, rel=1e-9)
    assert sim["curve"].iloc[0] == pytest.approx(100.0) and len(sim["trades"]) == 2
    start_value = 2 * tgt1  # value right after the first purchase, i.e. 100 minus its cost (the curve is rebased to 100 here)
    expected_end = tgt * px.at[idx[-1], "B"] / px.at[idx[20], "B"] / start_value * 100
    assert sim["curve"].iloc[-1] == pytest.approx(expected_end, rel=1e-9)  # after the switch only B compounds, net of cost and load


def test_exit_load_is_not_charged_on_units_held_long_enough():
    idx = pd.bdate_range("2020-01-01", periods=600)
    px = pd.DataFrame({"A": 100 * 1.0005 ** np.arange(600), "B": 100 * 1.0004 ** np.arange(600)}, index=idx)
    cfg = bt.BacktestConfig(strategy="equal_weight", cost_pct=0.0, exit_load_pct=1.0, exit_load_days=365, delay_days=0)
    held_long = bt._simulate(px, [(idx[0], idx[0], ["A"]), (idx[500], idx[500], ["B"])], cfg, costs=True)
    held_short = bt._simulate(px, [(idx[0], idx[0], ["A"]), (idx[100], idx[100], ["B"])], cfg, costs=True)
    assert held_long["load"] == 0.0 and held_short["load"] > 0.0


def test_too_few_eligible_funds_skips_rebalances_and_says_so(world):
    panel, rets, groups, hist, _ = world
    r = bt.run_backtest(panel, hist, set(list(panel.columns)[:3]), bt.BacktestConfig(strategy="multi_factor", top_n=5), rf_series(panel.index))
    assert r["available"] is False and "fewer than 3 rebalances" in r["reason"]


def test_unknown_strategy_is_rejected(world):
    with pytest.raises(ValueError):
        run(world, strategy="crystal_ball")


def test_every_strategy_runs_and_low_volatility_picks_lower_volatility(world):
    for s in bt.STRATEGIES:
        r = run(world, strategy=s, top_n=5)
        assert r["available"], s
    panel, rets, groups, hist, universe = world
    d = sorted(hist)[-1]
    low, _ = bt.select("low_volatility", hist[d], 5)
    assert hist[d].loc[low, "vol_3y"].mean() < hist[d]["vol_3y"].mean()
