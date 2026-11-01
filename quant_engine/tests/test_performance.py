import math

import numpy as np
import pandas as pd
import pytest
from quant_engine.common import clean_nav, returns

from quant_engine import performance as perf


def nav_from_returns(rets, start="2020-01-01", base=100.0):
    idx = pd.bdate_range(start, periods=len(rets) + 1)
    vals = [base]
    for r in rets:
        vals.append(vals[-1] * (1 + r))
    return pd.Series(vals, index=idx)


# ------------------------------------------------------------ returns & cleaning
def test_returns_drop_periods_spanning_a_data_gap():
    idx = pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03", "2024-02-01", "2024-02-02"])
    nav = pd.Series([100, 101, 102, 110, 111], index=idx)
    r = returns(nav)
    assert list(r.index.strftime("%m-%d")) == ["01-02", "01-03", "02-02"]  # the 29-day jump is not a one-day return


def test_clean_nav_removes_invalid_but_never_alters_values():
    idx = pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-03", "2024-01-04"])
    nav = pd.Series([100, -5, 101, 102, np.nan], index=idx)
    c = clean_nav(nav)
    assert list(c.values) == [100.0, 102.0]  # negative and NaN dropped, duplicate date keeps the last value


# ------------------------------------------------------------ cagr / total return
def test_cagr_matches_analytic_for_constant_daily_growth():
    idx = pd.date_range("2020-01-01", "2022-01-01", freq="D")  # calendar days, 731 days
    g = 0.0003
    nav = pd.Series(100 * (1 + g) ** np.arange(len(idx)), index=idx)
    days = (idx[-1] - idx[0]).days
    expected = ((nav.iloc[-1] / 100) ** (365.25 / days) - 1) * 100
    assert perf.cagr(nav).value == pytest.approx(expected, rel=1e-12)
    assert perf.total_return(nav).value == pytest.approx((nav.iloc[-1] / 100 - 1) * 100)


def test_cagr_of_a_doubling_over_two_years():
    idx = pd.to_datetime(["2020-01-01"] + list(pd.date_range("2020-01-02", "2021-12-31", freq="D"))[:-1] + ["2022-01-01"])
    nav = pd.Series(np.linspace(100, 200, len(idx)), index=idx)
    assert perf.cagr(nav).value == pytest.approx((2 ** (365.25 / 731) - 1) * 100)


def test_cagr_unavailable_for_short_history_with_reason():
    m = perf.cagr(nav_from_returns([0.01] * 10))
    assert m.value is None and "fewer than" in m.note


# ------------------------------------------------------------ trailing returns
def test_trailing_returns_use_the_right_anchor_dates_and_annualise_multi_year():
    idx = pd.bdate_range("2019-01-01", "2024-12-31")
    nav = pd.Series(np.arange(1, len(idx) + 1, dtype=float), index=idx)
    t = perf.trailing_returns(nav)
    end = idx[-1]
    anchor_1y = nav[:pd.Timestamp(end.year - 1, end.month, end.day)].iloc[-1]
    assert t["1y"].value == pytest.approx((nav.iloc[-1] / anchor_1y - 1) * 100)  # 1Y CAGR == simple 1Y return
    anchor_3y = nav[:pd.Timestamp(end.year - 3, end.month, end.day)].iloc[-1]
    assert t["3y"].value == pytest.approx(((nav.iloc[-1] / anchor_3y) ** (1 / 3) - 1) * 100)
    assert t["3y"].unit == "% p.a." and t["3m"].unit == "%"
    ytd_base = nav[:pd.Timestamp(end.year - 1, 12, 31)].iloc[-1]
    assert t["ytd"].value == pytest.approx((nav.iloc[-1] / ytd_base - 1) * 100)
    assert t["10y"].value is None and t["10y"].note == "not enough history"


# ------------------------------------------------------------ rolling returns
def test_rolling_returns_match_a_brute_force_loop():
    rng = np.random.default_rng(1)
    nav = nav_from_returns(rng.normal(0.0004, 0.01, 900), "2019-01-01")
    got = perf.rolling_returns(nav, 1)
    for t in got.index[::97]:
        start = pd.Timestamp(t.year - 1, t.month, t.day) if not (t.month == 2 and t.day == 29) else pd.Timestamp(t.year - 1, 2, 28)
        base = nav[:start].iloc[-1]
        assert got[t] == pytest.approx((nav[t] / base - 1) * 100)
    assert got.index[0] >= nav.index[0] + pd.Timedelta(days=358)  # no window without a full year behind it


def test_rolling_return_is_unavailable_when_the_start_anchor_is_in_a_gap():
    idx = list(pd.bdate_range("2020-01-01", "2020-03-01")) + list(pd.bdate_range("2021-03-02", "2021-04-01"))
    nav = pd.Series(np.linspace(100, 130, len(idx)), index=pd.DatetimeIndex(idx))
    r = perf.rolling_returns(nav, 1)
    # only the first days after the gap have an observation within 7 days before the window start
    assert r.index.min() == pd.Timestamp("2021-03-02") and r.index.max() < pd.Timestamp("2021-03-09")


def test_rolling_summary_statistics():
    s = pd.Series(np.arange(1.0, 101.0), index=pd.bdate_range("2020-01-01", periods=100))
    r = perf.rolling_summary(s)
    assert r["n"] == 100 and r["median"] == 50.5 and r["pct_positive"] == 100.0 and r["worst"] == 1.0
    assert perf.rolling_summary(pd.Series(dtype=float))["median"] is None


# ------------------------------------------------------------ calendar years
def test_calendar_returns_full_first_and_partial_years():
    idx = pd.to_datetime(["2022-06-01", "2022-12-30", "2023-06-01", "2023-12-29", "2024-03-01"])
    nav = pd.Series([100, 110, 120, 99, 108.9], index=idx)
    rows = {r["year"]: r for r in perf.calendar_returns(nav)}
    assert rows[2022]["partial"] is True and rows[2022]["return"] == pytest.approx(10.0)  # starts mid-year
    assert rows[2023]["partial"] is False and rows[2023]["return"] == pytest.approx((99 / 110 - 1) * 100)
    assert rows[2024]["partial"] is True and rows[2024]["return"] == pytest.approx((108.9 / 99 - 1) * 100)  # year to date


# ------------------------------------------------------------ benchmark relative
def test_tracking_error_and_information_ratio_against_manual_formulas():
    rng = np.random.default_rng(3)
    b = pd.Series(rng.normal(0.0004, 0.01, 500), index=pd.bdate_range("2020-01-01", periods=500))
    r = b + rng.normal(0.0002, 0.003, 500)
    active = (r - b).to_numpy()
    mean = sum(active) / len(active)
    var = sum((x - mean) ** 2 for x in active) / (len(active) - 1)
    te = math.sqrt(var) * math.sqrt(252) * 100
    assert perf.tracking_error(r, b).value == pytest.approx(te)
    assert perf.information_ratio(r, b).value == pytest.approx(mean * 252 / (math.sqrt(var) * math.sqrt(252)))


def test_fund_that_always_lags_by_a_constant_has_negative_excess_and_no_ir():
    idx = pd.bdate_range("2020-01-01", periods=200)
    b = pd.Series(np.tile([0.01, -0.005], 100), index=idx)
    r = b - 0.001
    m = perf.information_ratio(r, b)
    assert m.value is None and m.note == "zero tracking error"  # identical active return every day
    # with noise in the active return the sign of IR follows the sign of the average excess return
    r2 = b - 0.001 + pd.Series(np.tile([0.0005, -0.0005], 100), index=idx)
    assert perf.information_ratio(r2, b).value < 0


def test_capture_ratios_on_a_constructed_series():
    months = pd.period_range("2020-01", periods=36, freq="M")
    b_ret = np.where(np.arange(36) % 2 == 0, 0.02, -0.02)
    f_ret = np.where(b_ret > 0, 0.02, -0.01)  # captures 100% of up moves, 50% of down moves

    def month_end_nav(rets):
        idx = [p.to_timestamp(how="end").normalize() for p in months]
        return pd.Series(100 * np.cumprod(1 + np.array(rets)), index=pd.DatetimeIndex(idx))

    # prepend a base month so the first monthly return exists
    def with_base(s):
        return pd.concat([pd.Series([100.0], index=[s.index[0] - pd.offsets.MonthEnd(1)]), s])

    out = perf.capture_ratios(with_base(month_end_nav(f_ret)), with_base(month_end_nav(b_ret)))
    assert out["upside_capture"].value == pytest.approx(100.0)
    assert out["downside_capture"].value == pytest.approx(50.0)


def test_capture_unavailable_with_too_few_months():
    n = nav_from_returns([0.001] * 200)
    out = perf.capture_ratios(n, n)
    assert out["upside_capture"].value is None


def test_positive_month_frequency():
    idx = pd.to_datetime(["2020-01-31", "2020-02-29", "2020-03-31", "2020-04-30"] + [f"2020-{m:02d}-28" for m in range(5, 13)] + ["2021-01-29", "2021-02-26"])
    vals = [100, 101, 100, 102] + list(np.linspace(102, 110, 8)) + [111, 110]
    m = perf.positive_period_frequency(pd.Series(vals, index=pd.DatetimeIndex(idx)))
    changes = np.diff(vals)
    assert m.value == pytest.approx((changes > 0).mean() * 100)


def test_outperformance_frequency():
    idx = pd.bdate_range("2020-01-01", periods=100)
    f = pd.Series(np.r_[np.ones(70), np.zeros(30)], index=idx)
    b = pd.Series(0.5, index=idx)
    assert perf.outperformance_frequency(f, b).value == pytest.approx(70.0)
