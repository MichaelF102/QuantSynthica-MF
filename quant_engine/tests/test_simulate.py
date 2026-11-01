from datetime import date

import numpy as np
import pandas as pd
import pytest

from quant_engine import simulate as sm

IDX = pd.bdate_range("2015-01-01", "2025-12-31")


def flat(v=100.0):
    return pd.Series(v, index=IDX)


def grow(rate=0.0004):
    return pd.Series(100 * (1 + rate) ** np.arange(len(IDX)), index=IDX)


def test_xirr_known_cases():
    assert sm.xirr([(date(2021, 1, 1), -100), (date(2022, 1, 1), 200)]) == pytest.approx(1.0, rel=1e-6)  # exactly 365 days
    assert sm.xirr([(date(2020, 1, 1), -100), (date(2020, 7, 1), -100), (date(2021, 1, 1), 210)]) is not None
    assert sm.xirr([(date(2020, 1, 1), -100), (date(2021, 1, 1), 100)]) == pytest.approx(0.0, abs=1e-6)
    assert sm.xirr([(date(2020, 1, 1), -100), (date(2021, 1, 1), -50)]) is None  # no inflow: no rate exists


def test_lump_sum_matches_a_hand_calculation():
    n = grow()
    r = sm.lump_sum(n, 10000, pd.Timestamp("2016-01-01"), pd.Timestamp("2021-01-01"))
    s, e = n.loc["2016-01-01":].index[0], n.loc[:"2021-01-01"].index[-1]
    assert r["final_value"] == pytest.approx(10000 * n[e] / n[s]) and r["kind"] == "historical"
    assert r["cagr_pct"] == pytest.approx(((n[e] / n[s]) ** (365.25 / (e - s).days) - 1) * 100)


def test_sip_on_a_flat_nav_returns_exactly_what_was_invested():
    r = sm.sip(flat(), 5000, pd.Timestamp("2018-01-01"), pd.Timestamp("2020-12-31"))
    assert r["instalments"] == 36 and r["invested"] == 5000 * 36 and r["final_value"] == pytest.approx(r["invested"])
    assert r["xirr_pct"] == pytest.approx(0.0, abs=1e-4) and r["multiple"] == pytest.approx(1.0)


def test_sip_matches_a_reference_loop_and_supports_step_up_and_real_value():
    n = grow(0.0005)
    r = sm.sip(n, 1000, pd.Timestamp("2016-01-01"), pd.Timestamp("2018-12-31"), step_up_pct=10, inflation_pct=6)
    units, inv, last = 0.0, 0.0, n.loc[:"2018-12-31"].index[-1]
    for i, m in enumerate(pd.date_range("2016-01-01", "2018-12-01", freq="MS")):
        d = n.loc[m:].index[0]
        amt = 1000 * 1.1 ** (i // 12)
        units += amt / n[d]
        inv += amt
    assert r["invested"] == pytest.approx(inv) and r["final_value"] == pytest.approx(units * n[last])
    years = (last - n.loc["2016-01-01":].index[0]).days / 365.25
    assert r["final_value_real"] == pytest.approx(r["final_value"] / 1.06**years, rel=1e-9) and r["inflation_assumption_pct"] == 6


def test_sip_xirr_is_between_the_start_and_end_growth_rates():
    n = grow(0.0004)
    r = sm.sip(n, 1000, pd.Timestamp("2015-01-01"), pd.Timestamp("2025-12-31"))
    annual = (1.0004**252 - 1) * 100
    assert r["xirr_pct"] == pytest.approx(annual, rel=0.05)  # constant growth: every instalment earns the same rate


def test_swp_depletes_a_flat_corpus_in_exactly_the_right_month():
    r = sm.swp(flat(), 1000, 100, pd.Timestamp("2018-01-01"), pd.Timestamp("2020-12-31"))
    assert r["depleted"] and r["months_paid"] == 10 and r["total_withdrawn"] == pytest.approx(1000) and r["remaining_value"] == 0


def test_swp_on_growth_leaves_a_balance_and_inflation_raises_withdrawals():
    n = grow(0.0006)
    a = sm.swp(n, 100000, 500, pd.Timestamp("2016-01-01"), pd.Timestamp("2020-12-31"))
    b = sm.swp(n, 100000, 500, pd.Timestamp("2016-01-01"), pd.Timestamp("2020-12-31"), inflation_pct=8)
    assert not a["depleted"] and a["remaining_value"] > 100000
    assert b["total_withdrawn"] > a["total_withdrawn"] and b["remaining_value"] < a["remaining_value"]


def test_rolling_outcomes_are_ordered_labelled_historical_and_honest_about_short_history():
    rng = np.random.default_rng(1)
    n = pd.Series(100 * np.cumprod(1 + rng.normal(0.0004, 0.01, len(IDX))), index=IDX)
    r = sm.rolling_sip_outcomes(n, 1000, 3)
    p = r["xirr_pct"]
    assert r["kind"] == "historical" and p["p5"] <= p["p25"] <= p["median"] <= p["p75"] <= p["p95"] and r["worst_xirr_pct"] <= p["p5"]
    assert "overlap" in r["note"]
    assert not sm.rolling_sip_outcomes(n.iloc[:700], 1000, 3)["available"]
    s = sm.rolling_swp_survival(n, 200000, 1000, 5)
    assert 0 <= s["share_lasting_full_horizon"] <= 100


def test_projection_is_labelled_hypothetical_and_collapses_to_the_deterministic_value_without_volatility():
    z = sm.projection(10000, 10, 12, 0.0, paths=200)
    assert z["kind"] == "hypothetical" and z["percentiles"]["median"] == pytest.approx(z["deterministic_value"], rel=0.02)
    # monthly compounding of lognormal growth at 12% a year: check against the closed form for an annuity due
    g = 1.12 ** (1 / 12)
    assert z["deterministic_value"] == pytest.approx(10000 * sum(g ** (120 - i) for i in range(120)), rel=1e-6)
    a, b = sm.projection(10000, 10, 10, 8, paths=3000), sm.projection(10000, 10, 10, 20, paths=3000)
    assert (b["percentiles"]["p95"] - b["percentiles"]["p5"]) > (a["percentiles"]["p95"] - a["percentiles"]["p5"])
    assert a["percentiles"]["p5"] < a["percentiles"]["median"] < a["percentiles"]["p95"] and "not a forecast" in a["note"]
    assert sm.projection(5000, 5, 8, 12, seed=3) == sm.projection(5000, 5, 8, 12, seed=3)  # reproducible


def test_bootstrap_projection_resamples_history_and_refuses_short_series():
    r = pd.Series(np.random.default_rng(2).normal(0.0004, 0.01, 1500))
    a, b = sm.bootstrap_projection(r, 5000, 3, paths=300, seed=1), sm.bootstrap_projection(r, 5000, 3, paths=300, seed=1)
    assert a == b and a["kind"] == "hypothetical" and a["invested"] == 5000 * 36 and a["percentiles"]["p5"] < a["percentiles"]["p95"]
    assert not sm.bootstrap_projection(r.iloc[:300], 5000, 3)["available"]


def test_worst_episodes_find_the_planted_drawdowns_without_overlap():
    idx = pd.bdate_range("2016-01-01", periods=1200)
    v = np.full(1200, 100.0)
    v[:200] = np.linspace(100, 150, 200)
    v[200:260] = np.linspace(150, 90, 60)  # -40%
    v[260:600] = np.linspace(90, 160, 340)
    v[600:640] = np.linspace(160, 136, 40)  # -15%
    v[640:] = np.linspace(136, 200, 560)
    eps = sm.worst_episodes(pd.Series(v, index=idx), 3)
    assert eps[0]["fall_pct"] == pytest.approx(-40.0, abs=0.5) and eps[0]["peak"] == idx[200].date().isoformat()  # the last of two equal peak values
    assert eps[1]["fall_pct"] == pytest.approx(-15.0, abs=0.5)
    assert eps[0]["trough"] < eps[1]["peak"] or eps[1]["trough"] < eps[0]["peak"]


def test_window_return_and_beta_scenarios():
    n = grow(0.001)
    assert sm.window_return(n, "2020-01-02", "2020-03-02") == pytest.approx((n["2020-03-02"] / n["2020-01-02"] - 1) * 100)
    assert sm.window_return(n, "2001-01-01", "2002-01-01") is None  # before the data starts: no invented figure
    m = pd.Series(np.random.default_rng(4).normal(0.0003, 0.01, 800), index=pd.bdate_range("2020-01-01", periods=800))
    out = sm.beta_scenarios(1.5 * m, m, [-10, -20])
    assert out["kind"] == "hypothetical" and out["beta"] == pytest.approx(1.5) and out["scenarios"][1]["portfolio_change_pct"] == pytest.approx(-30.0)
    assert not sm.beta_scenarios(m.iloc[:100], m.iloc[:100], [-10])["available"]


def test_rebalance_plan_trades_net_to_new_cash_and_apply_exit_loads_only_when_due():
    cur = {"A": 600.0, "B": 300.0, "C": 100.0}
    tgt = {"A": 0.4, "B": 0.4, "C": 0.2}
    p = sm.rebalance_plan(cur, tgt, new_cash=100, threshold_pct=5, cost_pct=0.1, held_days={"A": 100, "B": 900}, exit_load_pct=1.0)
    buys = sum(t["amount"] for t in p["trades"] if t["action"] == "buy")
    sells = sum(t["amount"] for t in p["trades"] if t["action"] == "sell")
    assert buys - sells == pytest.approx(100.0) and p["rebalance_triggered"] and p["max_drift_pct"] == pytest.approx(20.0)
    a = next(t for t in p["trades"] if t["code"] == "A")
    assert a["action"] == "sell" and a["exit_load"] == pytest.approx(0.01 * a["amount"])  # A was held 100 days < 365
    assert p["estimated_fees"] == pytest.approx(sum(t["cost"] + t["exit_load"] for t in p["trades"]))
    assert sum(w["target_pct"] for w in p["weights"]) == pytest.approx(100.0)


def test_rebalance_plan_threshold_buys_only_and_validation():
    near = sm.rebalance_plan({"A": 505.0, "B": 495.0}, {"A": 0.5, "B": 0.5}, threshold_pct=5)
    assert not near["rebalance_triggered"]
    bo = sm.rebalance_plan({"A": 700.0, "B": 300.0}, {"A": 0.5, "B": 0.5}, new_cash=200, buys_only=True)
    assert all(t["action"] == "buy" for t in bo["trades"]) and sum(t["amount"] for t in bo["trades"]) <= 200 + 1e-9
    with pytest.raises(ValueError, match="sum to 100%"):
        sm.rebalance_plan({"A": 1.0}, {"A": 0.5})
    with pytest.raises(ValueError, match="positive"):
        sm.rebalance_plan({"A": 0.0}, {"A": 1.0})
