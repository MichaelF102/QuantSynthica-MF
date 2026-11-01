import math

import numpy as np
import pandas as pd
import pytest
from quant_engine.benchmark import category_index, risk_free_proxy
from quant_engine.common import returns

from quant_engine import analysis, risk


def series(vals, start="2020-01-01"):
    return pd.Series(vals, index=pd.bdate_range(start, periods=len(vals)), dtype=float)


def rnd(n=500, mu=0.0005, sd=0.01, seed=0):
    return series(np.random.default_rng(seed).normal(mu, sd, n))


# ------------------------------------------------------------ volatility / sharpe / sortino reference loops
def test_volatility_matches_a_manual_sample_standard_deviation():
    r = rnd()
    x = list(r)
    mean = sum(x) / len(x)
    sd = math.sqrt(sum((v - mean) ** 2 for v in x) / (len(x) - 1))
    assert risk.annualised_volatility(r).value == pytest.approx(sd * math.sqrt(252) * 100)


def test_sharpe_with_rf_series_and_constant_rate():
    r = rnd()
    rf = 0.07
    rfp = (1 + rf) ** (1 / 252) - 1
    ex = [v - rfp for v in r]
    mean = sum(ex) / len(ex)
    sd = math.sqrt(sum((v - mean) ** 2 for v in ex) / (len(ex) - 1))
    assert risk.sharpe_ratio(r, rf).value == pytest.approx(mean * 252 / (sd * math.sqrt(252)))
    rf_series = pd.Series(rfp, index=r.index)
    assert risk.sharpe_ratio(r, rf_series).value == pytest.approx(risk.sharpe_ratio(r, rf).value)
    assert risk.sharpe_ratio(r, 0.0).value > risk.sharpe_ratio(r, 0.20).value  # higher hurdle, lower Sharpe


def test_sortino_matches_a_manual_downside_deviation():
    r = rnd(seed=4)
    rf = 0.05
    rfp = (1 + rf) ** (1 / 252) - 1
    ex = [v - rfp for v in r]
    dd = math.sqrt(sum(min(v, 0) ** 2 for v in ex) / len(ex)) * math.sqrt(252)
    assert risk.sortino_ratio(r, rf).value == pytest.approx(sum(ex) / len(ex) * 252 / dd)
    assert risk.downside_deviation(r, 0.0).value == pytest.approx(math.sqrt(sum(min(v, 0) ** 2 for v in r) / len(r)) * math.sqrt(252) * 100)


def test_constant_returns_have_zero_volatility_and_undefined_ratios():
    r = series([0.001] * 100)
    assert risk.annualised_volatility(r).value == pytest.approx(0.0, abs=1e-9)
    s = risk.sharpe_ratio(r)
    assert s.value is None and s.note == "zero volatility"  # not infinity
    assert risk.sortino_ratio(r).value is None


def test_all_negative_returns_give_negative_sharpe():
    r = rnd(mu=-0.002, sd=0.003, seed=2)
    assert risk.sharpe_ratio(r).value < 0 and risk.sortino_ratio(r).value < 0


def test_too_few_observations_return_none_with_a_reason_never_zero():
    r = series([0.01] * 10)
    for m in (risk.annualised_volatility(r), risk.sharpe_ratio(r), risk.downside_deviation(r), risk.var_historical(r)):
        assert m.value is None and "fewer than" in m.note


def test_rolling_volatility_window():
    r = rnd(400)
    rv = risk.rolling_volatility(r, 252)
    assert len(rv) == 400 - 252 + 1
    assert rv.iloc[-1] == pytest.approx(r.iloc[-252:].std(ddof=1) * math.sqrt(252) * 100)


# ------------------------------------------------------------ drawdown
def test_max_drawdown_hand_computed_with_recovery():
    nav = series([100, 110, 120, 100, 90, 95, 118, 121, 125] + [126] * 25)
    d = risk.max_drawdown(nav)
    assert d["metric"].value == pytest.approx((90 / 120 - 1) * 100)  # -25%
    assert d["peak_date"] == nav.index[2].date() and d["trough_date"] == nav.index[4].date()
    assert d["recovery_date"] == nav.index[7].date()  # first value >= 120
    assert d["drawdown_days"] == (nav.index[4] - nav.index[2]).days
    assert d["recovery_days"] == (nav.index[7] - nav.index[4]).days
    assert d["current_drawdown"] == pytest.approx(0.0)


def test_drawdown_not_yet_recovered():
    nav = series([100, 120] + list(np.linspace(120, 60, 40)))
    d = risk.max_drawdown(nav)
    assert d["metric"].value == pytest.approx(-50.0) and d["recovery_date"] is None and d["recovery_days"] is None
    assert d["current_drawdown"] == pytest.approx(-50.0)


def test_extreme_drawdown_is_finite_and_bounded():
    nav = series([100] + list(np.linspace(100, 1, 60)))
    assert risk.max_drawdown(nav)["metric"].value == pytest.approx(-99.0)


def test_monotonic_rise_has_no_drawdown_and_no_calmar():
    nav = series(np.linspace(100, 150, 80))
    assert risk.max_drawdown(nav)["metric"].value == pytest.approx(0.0)
    assert risk.calmar_ratio(nav).value is None


def test_calmar_is_cagr_over_abs_max_drawdown():
    from quant_engine.performance import cagr

    nav = series(list(np.linspace(100, 130, 120)) + list(np.linspace(130, 100, 60)) + list(np.linspace(100, 170, 200)))
    assert risk.calmar_ratio(nav).value == pytest.approx(cagr(nav).value / abs(risk.max_drawdown(nav)["metric"].value))


# ------------------------------------------------------------ market risk
def test_beta_alpha_recover_a_constructed_relationship():
    b = rnd(400, seed=7)
    r = 0.0002 + 1.5 * b
    out = risk.beta_alpha(r, b)
    assert out["beta"].value == pytest.approx(1.5) and out["r_squared"].value == pytest.approx(1.0)
    assert out["alpha"].value == pytest.approx(0.0002 * 252 * 100)


def test_beta_with_risk_free_rate_uses_excess_returns():
    b = rnd(400, seed=8)
    rf = 0.06
    rfp = (1 + rf) ** (1 / 252) - 1
    r = rfp + 0.0001 + 0.8 * (b - rfp)
    out = risk.beta_alpha(r, b, rf)
    assert out["beta"].value == pytest.approx(0.8) and out["alpha"].value == pytest.approx(0.0001 * 252 * 100)


def test_beta_of_a_series_against_itself_is_one_and_correlation_one():
    r = rnd(300, seed=9)
    assert risk.beta_alpha(r, r)["beta"].value == pytest.approx(1.0)
    assert risk.correlation(r, r).value == pytest.approx(1.0)


def test_beta_unavailable_for_flat_benchmark_or_short_overlap():
    r = rnd(300, seed=1)
    assert risk.beta_alpha(r, series([0.0] * 300))["beta"].value is None
    assert risk.beta_alpha(r.iloc[:20], r.iloc[:20])["beta"].value is None


def test_beta_only_uses_overlapping_dates():
    b = rnd(300, seed=2)
    r = 1.2 * b
    shifted = r.copy()
    shifted.index = shifted.index + pd.Timedelta(days=1 * 7)  # same weekdays one week later: partial overlap
    out = risk.beta_alpha(shifted, b)
    assert out["beta"].n_obs < 300


# ------------------------------------------------------------ tail risk
def test_historical_var_cvar_against_manual_percentiles():
    r = series(np.arange(-50, 50) / 1000.0)  # -5% ... +4.9%, evenly spread
    x = sorted(r)
    k = 0.05 * (len(x) - 1)
    lo, hi = int(math.floor(k)), int(math.ceil(k))
    var95 = (x[lo] + (x[hi] - x[lo]) * (k - lo)) * 100
    assert risk.var_historical(r, 0.95).value == pytest.approx(var95)
    tail = [v for v in x if v <= var95 / 100]
    assert risk.cvar_historical(r, 0.95).value == pytest.approx(sum(tail) / len(tail) * 100)
    assert risk.cvar_historical(r, 0.95).value <= risk.var_historical(r, 0.95).value  # expected shortfall is at least as bad


def test_parametric_var_uses_the_normal_quantile():
    r = rnd(1000, mu=0.0003, sd=0.01, seed=5)
    expected = (r.mean() - 1.6448536269514722 * r.std(ddof=1)) * 100
    assert risk.var_parametric(r, 0.95).value == pytest.approx(expected, rel=1e-9)
    assert risk.var_parametric(r, 0.99).value < risk.var_parametric(r, 0.95).value


def test_skewness_and_kurtosis_against_manual_formulas():
    r = rnd(800, seed=6) ** 3 * 100  # heavy tails, skewed
    x = np.array(r)
    n = len(x)
    m = x.mean()
    s = x.std(ddof=1)
    g1 = (((x - m) ** 3).mean()) / (x.std(ddof=0) ** 3)
    skew = g1 * math.sqrt(n * (n - 1)) / (n - 2)
    g2 = ((x - m) ** 4).mean() / (x.std(ddof=0) ** 4) - 3
    kurt = ((n - 1) / ((n - 2) * (n - 3))) * ((n + 1) * g2 + 6)
    assert risk.skewness(r).value == pytest.approx(skew)
    assert risk.excess_kurtosis(r).value == pytest.approx(kurt)
    assert s > 0


# ------------------------------------------------------------ missing periods
def test_gap_in_the_series_does_not_inflate_volatility():
    idx = list(pd.bdate_range("2020-01-01", periods=150)) + list(pd.bdate_range("2020-12-01", periods=150))
    rng = np.random.default_rng(0)
    nav = pd.Series(100 * np.cumprod(1 + rng.normal(0.0003, 0.005, 300)), index=pd.DatetimeIndex(idx))
    r = returns(nav)
    assert len(r) == 298  # the return across the 8-month gap is dropped
    assert risk.annualised_volatility(r).value < 15


# ------------------------------------------------------------ benchmark proxies
def test_category_index_equals_the_common_fund_when_funds_are_identical():
    base = series(np.cumprod(1 + np.random.default_rng(1).normal(0.0004, 0.01, 200)) * 100)
    navs = {f"f{i}": base for i in range(6)}
    idx, n = category_index(navs, min_funds=5)
    assert n == 6
    assert returns(idx).to_numpy() == pytest.approx(returns(base).to_numpy())


def test_category_index_requires_enough_peers_and_can_exclude_the_fund():
    navs = {f"f{i}": series(np.linspace(100, 120, 60)) for i in range(5)}
    assert category_index(navs, min_funds=5)[0].empty is False
    assert category_index(navs, min_funds=5, exclude="f0")[0].empty  # only 4 peers left: no self-comparison, no thin index


def test_risk_free_proxy_is_the_median_not_the_mean():
    a, b, c = series([100, 101, 102, 103]), series([100, 100.5, 101, 101.5]), series([100, 120, 144, 172.8])  # c: +20% a day (below the 25% guard)
    rf, n = risk_free_proxy({"a": a, "b": b, "c": c}, min_funds=3)
    assert n == 3 and rf.iloc[0] == pytest.approx(0.01)  # median of 1%, 0.5%, 20%; the mean would be 7.2%


# ------------------------------------------------------------ whole analysis
def test_analyse_is_deterministic_and_carries_provenance():
    nav = series(100 * np.cumprod(1 + np.random.default_rng(11).normal(0.0004, 0.01, 1700)), "2019-01-01")
    bench = series(100 * np.cumprod(1 + np.random.default_rng(12).normal(0.0003, 0.009, 1700)), "2019-01-01")
    a1 = analysis.analyse(nav, bench, 0.06, rf_label="test", benchmark_label="test")
    a2 = analysis.analyse(nav, bench, 0.06, rf_label="test", benchmark_label="test")
    assert a1 == a2
    assert a1["methodology_version"] == "perf-risk-1.0.0" and a1["conventions"]["annualisation_periods"] == 252
    w3 = next(w for w in a1["windows"] if w["years"] == 3)
    for k in ("volatility", "sharpe_ratio", "max_drawdown", "var_95"):
        m = w3[k]
        assert m["window_start"] and m["window_end"] and m["n_obs"] > 600 and 0 < m["coverage"] <= 1
    assert "beta" in w3["benchmark"] and w3["benchmark"]["tracking_error"]["value"] > 0


def test_analyse_short_history_degrades_honestly():
    nav = series(100 * np.cumprod(1 + np.random.default_rng(1).normal(0.0004, 0.01, 200)))
    a = analysis.analyse(nav)
    assert a["available"] and [w["available"] for w in a["windows"]] == [False, False, False]
    assert a["trailing_returns"]["5y"]["value"] is None
    assert analysis.analyse(series([100, 101]))["available"] is False


def test_chart_series_are_downsampled_and_gaps_not_filled():
    nav = series(100 * np.cumprod(1 + np.random.default_rng(3).normal(0.0004, 0.01, 2500)), "2015-01-01")
    c = analysis.chart_series(nav, None, None)
    assert len(c["cumulative"]["fund"]) <= 601 and c["cumulative"]["fund"][0][1] == 100.0
    assert all(v <= 0 for _, v in c["drawdown"]["fund"])
    assert "1y" in c["rolling"] and "3y" in c["rolling"]


# ------------------------------------------------------------ data-quality guards
def test_suspect_nav_jump_is_detected_not_corrected():
    from quant_engine.common import suspect_moves

    nav = series(list(np.linspace(100, 110, 60)) + list(np.linspace(11, 12, 60)))  # 100 -> 11 in one step (-90%)
    bad = suspect_moves(nav)
    assert len(bad) == 1 and bad[0][1] < -0.85
    assert nav.iloc[59] == 110 and nav.iloc[60] == 11.0  # input untouched


def test_window_with_a_suspect_jump_is_unavailable_with_a_reason():
    vals = list(100 * np.cumprod(1 + np.random.default_rng(1).normal(0.0004, 0.01, 800)))
    vals[400:] = [v / 10 for v in vals[400:]]  # unit consolidation
    nav = series(vals, "2019-01-01")
    a = analysis.analyse(nav)
    w = next(w for w in a["windows"] if w["years"] == 1)
    assert w["available"] and a["data_issues"]  # latest year is after the jump: usable
    w3 = next(w for w in a["windows"] if w["years"] == 3)
    assert w3["available"] is False and w3["data_issue"] and "probable unit split" in w3["reason"]
    assert a["trailing_returns"]["3y"]["value"] is None and "NAV move" in a["trailing_returns"]["3y"]["note"]


def test_funds_with_suspect_jumps_are_left_out_of_peer_indices():
    good = {f"g{i}": series(np.linspace(100, 120, 80)) for i in range(5)}
    broken = series(list(np.linspace(100, 110, 40)) + list(np.linspace(11, 12, 40)))
    with_bad, n = category_index({**good, "bad": broken}, min_funds=5)
    assert n == 5  # the broken fund was not counted
    assert returns(with_bad).abs().max() < 0.05
    rf, m = risk_free_proxy({**good, "bad": broken}, min_funds=3)
    assert m == 5 and rf.abs().max() < 0.05


def test_ratios_are_not_reported_for_near_zero_volatility():
    r = series(np.random.default_rng(1).normal(0.0, 0.00002, 400))  # ~0.03% annual vol: money-market like
    for m in (risk.sharpe_ratio(r, 0.0), risk.sortino_ratio(r, 0.0)):
        assert m.value is None and "not meaningful" in m.note
    flat_bench = series(np.random.default_rng(2).normal(0.00025, 0.00002, 400))
    assert risk.beta_alpha(rnd(400, seed=3), flat_bench)["beta"].value is None


def test_a_jump_across_a_long_data_hole_is_not_a_suspect_move():
    from quant_engine.common import suspect_moves

    idx = list(pd.bdate_range("2015-01-01", periods=60)) + list(pd.bdate_range("2020-01-01", periods=60))
    vals = list(np.linspace(100, 105, 60)) + list(np.linspace(200, 210, 60))  # doubled while we have no data
    nav = pd.Series(vals, index=pd.DatetimeIndex(idx))
    assert suspect_moves(nav) == []  # unknown change over 5 years, not a one-day move
    assert len(returns(nav)) == 118  # and returns() already drops that gap-spanning return


def test_hand_written_moments_and_quantile_match_scipy():
    import numpy as np
    from scipy import stats

    from quant_engine.risk import NormalDist, _excess_kurtosis, _skew

    rng = np.random.default_rng(11)
    for n in (8, 60, 750):
        x = rng.standard_t(4, n) * 0.01
        assert abs(_skew(x) - stats.skew(x, bias=False)) < 1e-10
        assert abs(_excess_kurtosis(x) - stats.kurtosis(x, bias=False)) < 1e-10
    for q in (0.001, 0.01, 0.05, 0.5, 0.95):
        assert abs(NormalDist().inv_cdf(q) - stats.norm.ppf(q)) < 1e-9
