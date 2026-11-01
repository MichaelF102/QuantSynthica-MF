import math

import numpy as np
import pandas as pd
import pytest

from quant_engine import portfolio as pf


def rets(n=1000, k=5, seed=0, corr=0.3, vols=None, mus=None):
    rng = np.random.default_rng(seed)
    vols = np.array(vols if vols is not None else [0.006, 0.008, 0.01, 0.012, 0.014][:k])
    mus = np.array(mus if mus is not None else [0.0003] * k)
    c = np.full((k, k), corr) + np.eye(k) * (1 - corr)
    L = np.linalg.cholesky(c)
    x = rng.normal(0, 1, (n, k)) @ L.T * vols + mus
    return pd.DataFrame(x, index=pd.bdate_range("2019-01-01", periods=n), columns=[f"F{i}" for i in range(k)])


NO = pf.Limits()


def test_estimate_is_annualised_positive_definite_and_reports_its_window():
    r = rets()
    e = pf.estimate(r, lookback_days=2000)
    assert e.cov.shape == (5, 5) and np.allclose(e.cov, e.cov.T) and np.linalg.eigvalsh(e.cov).min() > 0
    assert e.cov[0, 0] == pytest.approx(0.006**2 * 252, rel=0.25)
    assert e.n_obs == 1000 and 0 < e.shrinkage_cov < 1 and e.start < e.end


def test_estimate_refuses_thin_data_and_warns_on_collinear_funds():
    with pytest.raises(pf.OptimisationError, match="at least 250"):
        pf.estimate(rets(n=120))
    with pytest.raises(pf.OptimisationError, match="at least two"):
        pf.estimate(rets(k=1, vols=[0.01]))
    r = rets(k=3, vols=[0.01, 0.01, 0.01])
    r["F2"] = r["F0"] * 1.0000001  # an almost identical fund
    e = pf.estimate(r, 2000)
    # Ledoit-Wolf shrinkage keeps even near-duplicate funds well-conditioned, so the covariance stays usable
    assert np.linalg.eigvalsh(e.cov).min() > 0 and e.condition_number < 1e6


def test_mean_return_shrinkage_pulls_toward_the_cross_section_mean():
    r = rets(mus=[0.0001, 0.0002, 0.0003, 0.0004, 0.0005])
    raw, shrunk = pf.estimate(r, 2000, shrink=0.0), pf.estimate(r, 2000, shrink=1.0)
    assert np.allclose(shrunk.mu, raw.mu_hist.mean()) and np.allclose(raw.mu, raw.mu_hist)
    assert any("Little shrinkage" in w for w in raw.warnings) and not any("Little shrinkage" in w for w in shrunk.warnings)


def test_min_variance_matches_the_closed_form_for_two_uncorrelated_assets():
    cov = np.diag([0.04, 0.01])
    w = pf.min_variance(cov, NO)
    assert w == pytest.approx([0.01 / 0.05, 0.04 / 0.05], abs=1e-5)


def test_unconstrained_tangency_matches_the_closed_form():
    cov = np.array([[0.04, 0.006, 0.002], [0.006, 0.09, 0.01], [0.002, 0.01, 0.0625]])
    mu = np.array([0.10, 0.14, 0.12])
    rf = 0.05
    ref = np.linalg.solve(cov, mu - rf)
    ref = ref / ref.sum()
    assert (ref > 0).all()
    assert pf.max_sharpe(mu, cov, rf, NO) == pytest.approx(ref, abs=2e-4)


def test_risk_parity_equalises_risk_contributions():
    cov = np.diag([0.01, 0.04, 0.09])
    w = pf.risk_parity(cov, NO)
    assert w == pytest.approx(np.array([6, 3, 2]) / 11, abs=1e-3)  # inverse volatility for uncorrelated assets
    c = pf.risk_decomposition(w, cov)["risk_contribution_pct"]
    assert max(c) - min(c) < 0.5 and sum(c) == pytest.approx(100.0)
    e = pf.estimate(rets(), 2000)
    rc = pf.risk_decomposition(pf.risk_parity(e.cov, NO), e.cov)["risk_contribution_pct"]
    assert max(rc) - min(rc) < 1.0  # also with correlated assets


def test_constraints_are_respected_bounds_sum_and_group_limits():
    e = pf.estimate(rets(k=6, vols=[0.006, 0.007, 0.008, 0.009, 0.010, 0.011]), 2000)
    lim = pf.Limits(min_w=0.05, max_w=0.30, groups=(((0, 1, 2), 0.0, 0.40),))
    for w in (pf.min_variance(e.cov, lim), pf.max_sharpe(e.mu, e.cov, 0.0, lim), pf.risk_parity(e.cov, lim)):
        assert w.sum() == pytest.approx(1.0) and w.min() >= 0.05 - 1e-6 and w.max() <= 0.30 + 1e-6 and w[:3].sum() <= 0.40 + 1e-6


def test_infeasible_constraints_are_rejected_with_a_reason():
    cov = np.eye(4) * 0.01
    for lim, msg in [(pf.Limits(max_w=0.2), "cannot reach 100%"), (pf.Limits(min_w=0.3), "exceeds 100%"),
                     (pf.Limits(max_w=0.3, max_funds=3), "cannot reach 100%"), (pf.Limits(min_w=0.5, max_w=0.2), "min <= max")]:
        with pytest.raises(pf.OptimisationError, match=msg):
            pf.min_variance(cov, lim)
    with pytest.raises(pf.OptimisationError, match="conflicts"):
        pf.min_variance(cov, pf.Limits(min_w=0.2, max_w=0.6, groups=(((0, 1), 0.0, 0.3),)))


def test_maximum_number_of_funds_is_enforced():
    e = pf.estimate(rets(k=8, vols=[0.006 + 0.001 * i for i in range(8)]), 2000)
    w = pf.min_variance(e.cov, pf.Limits(max_funds=3))
    assert (w > 1e-6).sum() <= 3 and w.sum() == pytest.approx(1.0)
    w = pf.max_sharpe(e.mu, e.cov, 0.0, pf.Limits(max_w=0.5, max_funds=3))
    assert (w > 1e-6).sum() <= 3 and w.max() <= 0.5 + 1e-6


def test_min_cvar_avoids_the_fund_with_crash_risk_and_reports_exact_cvar():
    rng = np.random.default_rng(3)
    T = 400
    a = rng.normal(0.0004, 0.005, T)
    b = rng.normal(0.0004, 0.005, T)
    c = rng.normal(0.0008, 0.004, T)
    c[:20] = -0.08  # rare, large losses
    S = np.column_stack([a, b, c])
    w, cvar = pf.min_cvar(S, NO, 0.95)
    assert w.sum() == pytest.approx(1.0) and w[2] < 0.15
    losses = np.sort(-(S @ w))[::-1]
    k = int(round(0.05 * T))
    assert cvar == pytest.approx(losses[:k].mean(), rel=1e-4)  # (1-alpha)*T is an integer, so the LP value is exact
    eq = np.full(3, 1 / 3)
    assert cvar < np.sort(-(S @ eq))[::-1][:k].mean()


def test_efficient_frontier_is_monotone_feasible_and_starts_at_min_variance():
    e = pf.estimate(rets(k=5, mus=[0.0001, 0.0002, 0.0003, 0.0004, 0.0005]), 2000, shrink=0.0)
    lim = pf.Limits(max_w=0.6)
    fr = pf.efficient_frontier(e.mu, e.cov, lim, points=15)
    assert len(fr) >= 10
    rets_, vols = [p["expected_return"] for p in fr], [p["volatility"] for p in fr]
    assert rets_ == sorted(rets_) and all(b >= a - 1e-6 for a, b in zip(vols, vols[1:]))
    wmin = pf.min_variance(e.cov, lim)
    assert vols[0] == pytest.approx(pf.stats(wmin, e.mu, e.cov)["volatility"], rel=1e-3)
    assert all(abs(sum(p["weights"]) - 1) < 1e-6 and max(p["weights"]) <= 0.6 + 1e-6 for p in fr)


def test_black_litterman_prior_and_view():
    cov = np.array([[0.04, 0.01], [0.01, 0.0625]])
    w = np.array([0.5, 0.5])
    prior = pf.black_litterman(cov, w, [])
    assert prior == pytest.approx(2.5 * cov @ w)
    post = pf.black_litterman(cov, w, [(np.array([1.0, 0.0]), prior[0] + 0.05)], view_uncertainty=1.0)
    assert post[0] > prior[0] and post[0] < prior[0] + 0.05  # moves toward the view without adopting it fully


def test_risk_decomposition_basics():
    cov = np.diag([0.04, 0.04, 0.04])
    d = pf.risk_decomposition(np.full(3, 1 / 3), cov)
    assert d["effective_number_of_funds"] == pytest.approx(3.0) and sum(d["risk_contribution_pct"]) == pytest.approx(100.0)
    assert d["diversification_ratio"] == pytest.approx(math.sqrt(3), rel=1e-6)


def test_portfolio_nav_buy_and_hold_and_rebalancing():
    idx = pd.bdate_range("2020-01-01", periods=300)
    panel = pd.DataFrame({"A": 100 * 1.001 ** np.arange(300), "B": 100 * 1.0002 ** np.arange(300)}, index=idx)
    bh = pf.portfolio_nav(panel, {"A": 0.5, "B": 0.5}, "none")
    assert bh.iloc[-1] == pytest.approx(100 * (0.5 * panel.A.iloc[-1] / panel.A.iloc[0] + 0.5 * panel.B.iloc[-1] / panel.B.iloc[0]))
    rb = pf.portfolio_nav(panel, {"A": 0.5, "B": 0.5}, "M")
    assert rb.iloc[-1] < bh.iloc[-1]  # rebalancing sells the winner, so it ends lower in a steadily trending market
    late = panel.copy()
    late.loc[late.index[:100], "B"] = np.nan
    assert pf.portfolio_nav(late, {"A": 0.5, "B": 0.5}, "M").index[0] == idx[100]  # starts when every fund exists


def test_holdout_check_fits_only_on_data_before_the_cutoff():
    r = rets(n=1200, k=4, seed=5)
    seen = {}

    def solver(est, lim):
        seen["end"] = est.end
        return pf.min_variance(est.cov, lim)

    out = pf.holdout_check(r, solver, NO, holdout_days=300, lookback_days=900)
    assert out["available"] and out["fit_end"] < out["holdout_start"] and seen["end"] <= out["fit_end"]
    assert set(out) >= {"optimised", "equal_weight", "observations", "note"}
    assert not pf.holdout_check(r.iloc[:300], solver, NO)["available"]


def test_ledoit_wolf_matches_scikit_learn():
    from sklearn.covariance import LedoitWolf

    from quant_engine.portfolio import ledoit_wolf

    rng = np.random.default_rng(3)
    for n, p in [(300, 5), (800, 12), (260, 30)]:
        X = rng.normal(0, 0.01, (n, p)) @ rng.normal(0, 1, (p, p)) * 0.3 + rng.normal(0, 0.005, (n, p))
        cov, s = ledoit_wolf(X)
        ref = LedoitWolf().fit(X)
        assert np.allclose(cov, ref.covariance_, rtol=1e-10, atol=1e-14) and abs(s - ref.shrinkage_) < 1e-12
