import numpy as np
import pandas as pd
import pytest
from tests.synth import make_panel

from quant_engine import clustering, regime


def market(seed=0, n=3500):
    rng = np.random.default_rng(seed)
    r = np.concatenate([rng.normal(0.0008, 0.006, n // 3), rng.normal(-0.0007, 0.014, n // 3), rng.normal(0.0004, 0.008, n - 2 * (n // 3))])
    return pd.Series(100 * np.cumprod(1 + r), index=pd.bdate_range("2010-01-01", periods=n), name="m")


def test_trend_regime_labels_a_rally_bull_and_a_slump_bear():
    idx = pd.bdate_range("2015-01-01", periods=700)
    up = pd.Series(np.linspace(100, 200, 700), index=idx)
    down = pd.Series(np.linspace(200, 100, 700), index=idx)
    assert regime.trend_regime(up).iloc[-1] == "bull" and regime.trend_regime(down).iloc[-1] == "bear"
    assert regime.trend_regime(up).iloc[:150].isna().all()  # not enough history for the 200-day average yet


def test_vol_and_trend_regimes_are_point_in_time():
    m = market()
    cut = 2500
    for fn in (regime.vol_regime, regime.trend_regime):
        full, part = fn(m), fn(m.iloc[:cut])
        pd.testing.assert_series_equal(full.iloc[:cut], part, check_names=False)  # later data cannot relabel the past


def test_hmm_uses_filtered_probabilities_so_the_future_cannot_change_past_labels():
    m = market()
    n_ret = len(m) - 1
    n_train = int(n_ret * 0.6)
    full = regime.hmm_regimes(m, 3, 0.6)
    cut = n_train + 400
    part = regime.hmm_regimes(m.iloc[: cut + 1], 3, (n_train + 1e-6) / cut)  # same training window, less future
    assert part["train_end"] == full["train_end"]
    a, b = full["labels"].iloc[:cut], part["labels"]
    assert (a.index == b.index).all() and (a.to_numpy() == b.to_numpy()).all()
    assert set(full["labels"]) <= {"calm", "moderate", "turbulent"} and "fitted on data to" in full["note"]
    sp = full["state_params"]
    assert sp["calm"]["vol_daily_pct"] < sp["moderate"]["vol_daily_pct"] < sp["turbulent"]["vol_daily_pct"]  # named by volatility
    assert full["probabilities"].sum(axis=1).round(6).eq(1).all()


def test_regime_stats_and_transition_matrix():
    m = market()
    lab = regime.trend_regime(m)
    stats = regime.regime_stats(m, lab)
    assert sum(s["share"] for s in stats) == pytest.approx(1.0, abs=0.02) or sum(s["share"] for s in stats) <= 1.0
    bear = next(s for s in stats if s["regime"] == "bear")
    bull = next(s for s in stats if s["regime"] == "bull")
    assert bear["annualised_return"] < bull["annualised_return"]
    t = regime.transition_matrix(lab)
    assert np.allclose(np.array(t["matrix"]).sum(axis=1), 1.0, atol=1e-3)


def test_market_index_requires_enough_funds():
    panel, rets, groups = make_panel(n_funds=8, years=3, seed=1)
    assert len(regime.market_index(rets, list(rets.columns), min_funds=5)) > 500
    assert regime.market_index(rets, list(rets.columns)[:3], min_funds=5).empty


# ------------------------------------------------------------ clustering
def blobs(seed=0, per=30):
    rng = np.random.default_rng(seed)
    centers = {"a": [20, 25, 0.8, -30, 15, 90, 0.5], "b": [8, 10, 0.4, -12, 5, 50, -0.2], "c": [14, 17, 0.6, -20, 10, 70, 0.1]}
    rows, codes = [], []
    for k, c in centers.items():
        for i in range(per):
            rows.append(np.array(c) + rng.normal(0, [1.2, 1.5, 0.05, 2, 1.5, 6, 0.08]))
            codes.append(f"{k}{i}")
    return pd.DataFrame(rows, index=codes, columns=clustering.FEATURES)


def test_clustering_recovers_three_well_separated_groups():
    r = clustering.cluster_tier(blobs())
    km = next(m for m in r["methods"] if m["method"] == "kmeans")
    assert r["available"] and km["clusters"] == 3 and km["silhouette"] > 0.6
    groups = {}
    for code, lab in km["assignments"].items():
        groups.setdefault(code[0], set()).add(lab)
    assert all(len(v) == 1 for v in groups.values()) and len({next(iter(v)) for v in groups.values()}) == 3
    assert {m["method"] for m in r["methods"]} == {"kmeans", "hierarchical", "gmm", "dbscan"}
    assert 0 < sum(r["pca"]["explained_variance"]) <= 1


def test_clustering_is_deterministic_and_labels_describe_traits():
    a, b = clustering.cluster_tier(blobs()), clustering.cluster_tier(blobs())
    assert a["methods"][0]["assignments"] == b["methods"][0]["assignments"]
    labels = [c["label"] for c in a["methods"][0]["centroids"]]
    assert any("high return" in l for l in labels) and any("low return" in l for l in labels)


def test_small_tiers_are_not_clustered_and_outliers_do_not_define_clusters():
    assert clustering.cluster_tier(blobs(per=5))["available"] is False
    df = blobs()
    df.loc["a0"] = [900, 900, 50, -99, 500, 900, 9]  # absurd outlier is winsorised
    r = clustering.cluster_tier(df)
    km = next(m for m in r["methods"] if m["method"] == "kmeans")
    assert km["clusters"] == 3 and km["silhouette"] > 0.5


def test_regime_statistics_use_the_next_days_return_not_the_return_that_set_the_label():
    rng = np.random.default_rng(4)
    r = pd.Series(rng.normal(0, 0.01, 2000), index=pd.bdate_range("2015-01-01", periods=2000))
    idx = 100 * (1 + r).cumprod()
    labels = pd.Series(np.where(r > 0, "up", "down"), index=idx.index)  # a label set by the same day's return
    stats = {s["regime"]: s for s in regime.regime_stats(idx, labels)}
    # same-day attribution would show up-days at roughly +60% a year and down-days at -60%; the next day's return is noise
    assert abs(stats["up"]["annualised_return"]) < 25 and abs(stats["down"]["annualised_return"]) < 25
