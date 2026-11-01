import numpy as np
import pandas as pd
import pytest
from quant_engine.common import returns
from tests.synth import make_panel, rf_series

from quant_engine import performance as perf
from quant_engine import risk, scoring


@pytest.fixture(scope="module")
def world():
    panel, rets, groups = make_panel(n_funds=14, years=7, seed=1, groups=2)
    rf = rf_series(rets.index)
    asof = rets.index[-1]
    return panel, rets, groups, rf, asof, scoring.factor_metrics(rets, rf, asof, groups)


def test_vectorised_metrics_agree_with_the_scalar_engine(world):
    panel, rets, groups, rf, asof, m = world
    for code in ["F00", "F05", "F11"]:
        nav = panel[code]
        w = nav.loc[nav.index > asof - pd.Timedelta(days=365 * 3 + 1)]
        r = returns(w)
        assert m.loc[code, "vol_3y"] == pytest.approx(risk.annualised_volatility(r).value, rel=0.02)
        assert m.loc[code, "max_dd_3y"] == pytest.approx(risk.max_drawdown(w)["metric"].value, rel=0.03)
        assert m.loc[code, "sharpe_3y"] == pytest.approx(risk.sharpe_ratio(r, rf).value, rel=0.04, abs=0.03)
        assert m.loc[code, "sortino_3y"] == pytest.approx(risk.sortino_ratio(r, rf).value, rel=0.04, abs=0.03)
        assert m.loc[code, "ret_3y"] == pytest.approx(perf.trailing_returns(nav)["3y"].value, rel=0.03)
        assert m.loc[code, "mom_12m"] == pytest.approx(perf.trailing_returns(nav)["1y"].value, rel=0.03, abs=0.2)


def test_metrics_use_only_information_up_to_asof(world):
    panel, rets, groups, rf, asof, _ = world
    cut = rets.index[-400]
    truncated = rets.loc[:cut]
    mutated = rets.copy()
    mutated.loc[mutated.index > cut] = np.random.default_rng(5).normal(0.05, 0.1, mutated.loc[mutated.index > cut].shape)  # wild future
    a = scoring.factor_metrics(truncated, rf, cut, groups)
    b = scoring.factor_metrics(mutated, rf, cut, groups)
    pd.testing.assert_frame_equal(a, b)
    sa, sb = scoring.score_universe(a[scoring.METRIC_KEYS], groups), scoring.score_universe(b[scoring.METRIC_KEYS], groups)
    pd.testing.assert_frame_equal(sa, sb)


def test_percentiles_are_direction_aware_and_bounded(world):
    *_, m = world
    sc = scoring.score_universe(m[scoring.METRIC_KEYS], world[2])
    grp = sc[sc["group"] == "G0"]
    p = grp.filter(like="p_")
    assert p.min().min() >= 0 and p.max().max() <= 100
    best_ret = m.loc[grp.index, "ret_3y"].idxmax()
    assert grp.loc[best_ret, "p_ret_3y"] == pytest.approx(100.0)
    lowest_dd = m.loc[grp.index, "downside_dev_3y"].idxmin()  # lower downside deviation is better
    assert grp.loc[lowest_dd, "p_downside_dev_3y"] == pytest.approx(100.0)
    shallow = m.loc[grp.index, "max_dd_3y"].idxmax()  # a less negative drawdown is better
    assert grp.loc[shallow, "p_max_dd_3y"] == pytest.approx(100.0)


def test_composite_is_the_weighted_sum_of_factor_scores_with_coverage(world):
    *_, m = world
    sc = scoring.score_universe(m[scoring.METRIC_KEYS], world[2])
    assert (sc["composite"].between(0, 100)).all()
    assert (sc["coverage"] <= 0.95 + 1e-9).all()  # Stability (5%) cannot be computed from NAV
    assert sc["f_stability"].isna().all()
    avail_w = sum(w for f, w in scoring.WEIGHTS.items() if f != "stability")
    manual = sum(sc[f"f_{f}"] * scoring.WEIGHTS[f] for f in scoring.FACTORS if f != "stability") / avail_w
    assert sc["composite"].to_numpy() == pytest.approx(manual.to_numpy())
    assert sc[[c for c in sc if c.startswith("c_")]].sum(axis=1).to_numpy() == pytest.approx(sc["composite"].to_numpy())


def test_missing_metrics_are_not_filled_with_zero(world):
    *_, m = world
    groups = world[2]
    m2 = m[scoring.METRIC_KEYS].copy()
    victim = "F00"
    m2.loc[victim, ["ret_5y", "sharpe_3y", "sortino_3y"]] = np.nan
    sc = scoring.score_universe(m2, groups)
    assert np.isnan(sc.loc[victim, "p_ret_5y"])
    assert sc.loc[victim, "f_performance"] == pytest.approx(sc.loc[victim, ["p_ret_1y", "p_ret_3y"]].mean())  # mean of what exists
    assert sc.loc[victim, "composite"] > 0


def test_funds_with_too_little_data_are_unscored_not_zero_scored(world):
    *_, m = world
    groups = world[2]
    m2 = m[scoring.METRIC_KEYS].copy()
    m2.loc["F01"] = np.nan
    sc = scoring.score_universe(m2, groups)
    assert np.isnan(sc.loc["F01", "composite"]) and sc.loc["F01", "coverage"] == 0


def test_small_peer_groups_are_not_scored(world):
    *_, m = world
    tiny = pd.Series({c: ("A" if i < 3 else "B") for i, c in enumerate(m.index)})
    sc = scoring.score_universe(m[scoring.METRIC_KEYS], tiny)
    assert "A" not in set(sc["group"])


def test_outlier_is_winsorised_in_z_scores_but_not_in_ranks(world):
    *_, m = world
    groups = world[2]
    m2 = m[scoring.METRIC_KEYS].copy()
    base = scoring.score_universe(m2, groups)
    m2.loc["F00", "ret_3y"] = 1e6
    out = scoring.score_universe(m2, groups)
    g = out[out["group"] == "G0"]
    assert g["z_ret_3y"].abs().max() < 5  # the outlier is clipped before z-scoring
    assert out.loc["F00", "p_ret_3y"] == pytest.approx(100.0)
    others = [c for c in g.index if c != "F00"]
    assert out.loc[others, "p_ret_1y"].equals(base.loc[others, "p_ret_1y"])  # other metrics untouched
