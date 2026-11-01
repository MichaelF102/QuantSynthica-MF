

def test_aggregate_benchmark_equals_direct_leave_one_out():
    import numpy as np
    import pandas as pd

    from quant_engine.benchmark import category_aggregate, category_index, category_index_from_aggregate

    rng = np.random.default_rng(5)
    navs = {}
    for k in range(9):
        n = 900 - 70 * k                                    # staggered start dates: counts change over time
        idx = pd.bdate_range("2019-01-01", periods=1000)[1000 - n:]
        navs[f"F{k}"] = pd.Series(100 * np.cumprod(1 + rng.normal(0.0004, 0.01, n)), index=idx)
    bad = navs["F2"].copy()
    bad.iloc[400:] *= 0.4                                    # a split-like jump makes F8 'suspect': it must be left out
    navs["F2"] = bad
    total, count, members = category_aggregate(navs)
    assert "F2" not in members and len(members) == 8
    for own in ["F0", "F5", "F2", "NEW"]:                   # member, late-start member, suspect non-member, outsider
        own_nav = navs.get(own, navs["F1"] * 1.01)
        direct, n_direct = category_index({k: v for k, v in navs.items() if k != own}, 5)
        fast, n_fast = category_index_from_aggregate(total, count, members, 5, own_code=own, own_nav=own_nav)
        assert n_direct == n_fast, own
        assert (direct.index == fast.index).all(), own
        assert np.allclose(direct.to_numpy(), fast.to_numpy(), rtol=1e-9), own
    # too few peers once the fund itself is excluded
    t2, c2, m2 = category_aggregate({k: navs[k] for k in ["F0", "F1", "F3", "F4", "F5"]})
    idx, n = category_index_from_aggregate(t2, c2, m2, 5, own_code="F0", own_nav=navs["F0"])
    assert idx.empty and n == 4
