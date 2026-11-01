"""Phase 6 API on a synthetic universe (no network)."""
import os

import numpy as np
import pandas as pd
import pytest
from app.core.config import get_settings
from app.models import AmfiScheme, Scheme, SchemeMapping
from app.services import analytics, quant
from data_pipeline.nav.store import NavStore
from fastapi.testclient import TestClient
from sqlalchemy import select, text


@pytest.fixture(scope="module")
def world(migrated, loaded, tmp_path_factory):
    from app.db import session_factory

    tmp = tmp_path_factory.mktemp("phase6")
    old = os.environ.get("QSMF_DATA_DIR")
    os.environ["QSMF_DATA_DIR"] = str(tmp)
    get_settings.cache_clear()
    analytics._rf_cached.cache_clear()
    quant._bundle_cache.clear()
    with session_factory()() as s:
        for t in ("fund_scores", "backtest_runs", "scheme_metrics", "scheme_mappings", "nav_coverage", "amfi_schemes"):
            s.execute(text(f"delete from {t}"))
        s.commit()

        def pick(cat, n, tier=None):
            q = (select(Scheme).join(Scheme.category).where(Scheme.plan_type == "Direct", Scheme.option_type == "Growth", Scheme.is_insurer_fund.is_(False))
                 .where(text(f"fund_categories.name = '{cat}'")).order_by(Scheme.id).limit(n))
            return list(s.scalars(q))

        flexi, large = pick("Flexi Cap", 8), pick("Large-Cap", 4)
        liquid = pick("Liquid", 4) or pick("Overnight", 4)
        idcw = s.scalars(select(Scheme).where(Scheme.option_type == "IDCW", Scheme.is_insurer_fund.is_(False)).limit(1)).one()
        short, unmapped = None, s.scalars(select(Scheme).where(Scheme.option_type == "Growth", Scheme.is_insurer_fund.is_(False),
                                                                Scheme.id.notin_([f.id for f in flexi + large + liquid])).limit(2)).all()
        short, unmapped = unmapped[0], unmapped[1]
        store = NavStore(tmp / "silver" / "nav")
        idx = pd.bdate_range("2014-01-01", "2026-10-30")
        rng = np.random.default_rng(21)
        market = rng.normal(0.0004, 0.008, len(idx))
        market[1500:1560] = rng.normal(-0.01, 0.012, 60)  # a planted crash
        out, k = {}, 0
        for group, funds in (("flexi", flexi), ("large", large), ("liquid", liquid), ("idcw", [idcw]), ("short", [short])):
            for f in funds:
                code = str(920000 + k)
                k += 1
                if group == "liquid":
                    r = rng.normal(0.00025, 0.00003, len(idx))
                else:
                    r = rng.normal(0.0001 * (k % 4), 0.004, len(idx)) + 0.8 * market
                nav = 100 * np.cumprod(1 + r)
                dates = idx if group != "short" else idx[-150:]  # a fund too new for a 250-day lookback
                vals = nav if group != "short" else nav[-150:]
                s.add(AmfiScheme(code=code, name=f.name, amc="x", latest_nav=float(vals[-1])))
                s.flush()
                s.add(SchemeMapping(scheme_id=f.id, amfi_code=code, variant="growth" if f.option_type == "Growth" else "idcw_payout", status="confirmed", method="t", matcher_version="t"))
                store.upsert((code, d.date(), float(v), "t") for d, v in zip(dates, vals))
                out.setdefault(group, []).append(f.id)
        s.add(SchemeMapping(scheme_id=unmapped.id, amfi_code=None, status="unmapped", method="t", matcher_version="t"))
        s.commit()
    out["unmapped"] = unmapped.id
    yield out
    if old is None:
        os.environ.pop("QSMF_DATA_DIR", None)
    else:
        os.environ["QSMF_DATA_DIR"] = old
    get_settings.cache_clear()
    quant._bundle_cache.clear()


def api():
    from app.main import app

    return TestClient(app)


def holdings(ids, w=None):
    return [{"scheme_id": i, "weight": (w[k] if w else 1)} for k, i in enumerate(ids)]


# ------------------------------------------------------------------ analyze
def test_analyze_normalises_weights_and_reports_allocation_and_risk(world):
    ids = world["flexi"][:4] + world["large"][:2]
    r = api().post("/api/v1/portfolio/analyze", json={"holdings": holdings(ids, [2, 2, 2, 2, 1, 1])})
    assert r.status_code == 200
    d = r.json()
    assert sum(f["weight_pct"] for f in d["funds"]) == pytest.approx(100.0) and d["funds"][0]["weight_pct"] == pytest.approx(20.0)
    assert sum(a["weight_pct"] for a in d["allocation"]["by_category"]) == pytest.approx(100.0)
    assert {a["name"] for a in d["allocation"]["by_category"]} == {"Flexi Cap", "Large-Cap"}
    assert sum(d["risk"]["risk_contribution_pct"]) == pytest.approx(100.0) and 1 < d["risk"]["effective_number_of_funds"] < 6
    m = np.array(d["risk"]["correlation"]["matrix"])
    assert np.allclose(np.diag(m), 1.0) and (m > 0.3).all()
    assert d["analytics"]["available"] and "Equal-weighted mix" in d["analytics"]["conventions"]["benchmark"]
    assert d["charts"]["cumulative"]["fund"][0][1] == 100.0 and d["history"]["start"] <= d["history"]["end"]


def test_analyze_rejects_bad_requests_with_a_reason(world):
    c = api()
    ok = world["flexi"][:2]
    cases = [
        ({"holdings": []}, "at least one"), ({"holdings": holdings([ok[0], ok[0]])}, "more than once"),
        ({"holdings": holdings(ok, [1, -1])}, "zero or positive"), ({"holdings": holdings(ok, [0, 0])}, "more than zero"),
        ({"holdings": holdings([world["idcw"][0]])}, "cannot be used"), ({"holdings": holdings([world["unmapped"]])}, "cannot be used"),
        ({"holdings": holdings(ok), "rebalance": "weekly"}, "rebalance must be"), ({"holdings": [{"scheme_id": 1}]}, "invalid request"),
    ]
    for body, msg in cases:
        r = c.post("/api/v1/portfolio/analyze", json=body)
        assert r.status_code == 422 and msg in r.json()["detail"], (body, r.text)


# ------------------------------------------------------------------ optimize
@pytest.mark.parametrize("method", ["equal_weight", "min_variance", "max_sharpe", "risk_parity", "min_cvar"])
def test_every_method_returns_valid_weights_assumptions_and_a_holdout(world, method):
    ids = world["flexi"][:5] + world["large"][:3]
    r = api().post("/api/v1/portfolio/optimize", json={"scheme_ids": ids, "method": method, "limits": {"max_weight_pct": 40, "min_weight_pct": 2}})
    assert r.status_code == 200, r.text
    d = r.json()
    w = np.array([f["weight_pct"] for f in d["funds"]]) / 100
    assert w.sum() == pytest.approx(1.0) and w.max() <= 0.40 + 1e-6 and w.min() >= 0.02 - 1e-6
    a = d["assumptions"]
    assert a["covariance"] == "Ledoit-Wolf shrinkage" and a["mean_return_shrinkage"] == 0.5 and a["estimation_window"]["observations"] > 700
    assert d["holdout"]["available"] and d["holdout"]["fit_end"] < d["holdout"]["holdout_start"]
    assert any("not forecasts" in x for x in d["warnings"]) and d["method"] == method
    assert sum(d["risk"]["risk_contribution_pct"]) == pytest.approx(100.0)


def test_min_variance_is_no_riskier_than_equal_weight_and_the_frontier_is_consistent(world):
    ids = world["flexi"][:5] + world["large"][:3]
    mv = api().post("/api/v1/portfolio/optimize", json={"scheme_ids": ids, "method": "min_variance"}).json()
    ew = api().post("/api/v1/portfolio/optimize", json={"scheme_ids": ids, "method": "equal_weight"}).json()
    assert mv["stats"]["volatility"] <= ew["stats"]["volatility"] + 1e-6
    fr = mv["frontier"]
    assert len(fr) >= 10 and [p["expected_return"] for p in fr] == sorted(p["expected_return"] for p in fr)
    assert fr[0]["volatility"] == pytest.approx(mv["stats"]["volatility"], rel=0.02) and "frontier" not in api().post(
        "/api/v1/portfolio/optimize", json={"scheme_ids": ids, "method": "min_cvar"}).json()


def test_category_limits_and_max_funds_are_enforced(world):
    ids = world["flexi"][:5] + world["large"][:3]
    resp = api().post("/api/v1/portfolio/optimize", json={"scheme_ids": ids, "method": "max_sharpe", "limits": {"category_max_pct": 60, "max_weight_pct": 50}})
    assert resp.status_code == 200, resp.text
    r = resp.json()
    by_cat = {}
    for f in r["funds"]:
        by_cat[f["category"]] = by_cat.get(f["category"], 0) + f["weight_pct"]
    assert max(by_cat.values()) <= 60 + 1e-4
    r = api().post("/api/v1/portfolio/optimize", json={"scheme_ids": ids, "method": "min_variance", "limits": {"max_funds": 3}}).json()
    assert sum(1 for f in r["funds"] if f["weight_pct"] > 1e-4) <= 3


def test_infeasible_and_invalid_optimisations_explain_themselves(world):
    c, ids = api(), world["flexi"][:4]
    bad = [
        ({"scheme_ids": ids, "limits": {"max_weight_pct": 20}}, "cannot reach 100%"), ({"scheme_ids": ids[:1]}, "at least two"),
        ({"scheme_ids": ids, "method": "magic"}, "method must be"), ({"scheme_ids": ids, "lookback_years": 50}, "lookback_years"),
        ({"scheme_ids": ids, "method": "black_litterman"}, "at least one view"),
        ({"scheme_ids": ids + [world["short"][0]]}, "at least 250"), ({"scheme_ids": ids + [world["idcw"][0]]}, "cannot be used"),
        ({"scheme_ids": ids, "limits": {"min_weight_pct": 30}}, "exceeds 100%"),
    ]
    for body, msg in bad:
        r = c.post("/api/v1/portfolio/optimize", json=body)
        assert r.status_code == 422 and msg in r.json()["detail"], (body, r.text)


def test_black_litterman_moves_expected_return_toward_the_view(world):
    ids = world["flexi"][:4]
    base = {"scheme_ids": ids, "method": "black_litterman"}
    lo = api().post("/api/v1/portfolio/optimize", json={**base, "views": [{"scheme_id": ids[0], "annual_return_pct": 0}]}).json()
    hi = api().post("/api/v1/portfolio/optimize", json={**base, "views": [{"scheme_id": ids[0], "annual_return_pct": 40}]}).json()
    wl = next(f["weight_pct"] for f in lo["funds"] if f["scheme_id"] == ids[0])
    wh = next(f["weight_pct"] for f in hi["funds"] if f["scheme_id"] == ids[0])
    assert wh > wl and any("equal-weight reverse optimisation" in x for x in hi["warnings"])
    r = api().post("/api/v1/portfolio/optimize", json={**base, "views": [{"scheme_id": 1, "annual_return_pct": 5}]})
    assert r.status_code == 422 and "not selected" in r.json()["detail"]


# ------------------------------------------------------------------ simulate
def test_historical_simulators_are_labelled_and_consistent(world):
    f = world["flexi"][0]
    c = api()
    s = c.post("/api/v1/portfolio/simulate", json={"kind": "sip", "target": {"scheme_id": f}, "monthly": 5000, "start": "2018-01-01", "end": "2020-12-31"}).json()
    assert s["kind"] == "historical" and "actual NAV history" in s["label"] and s["instalments"] == 36 and s["invested"] == 5000 * 36
    assert s["final_value"] == pytest.approx(s["invested"] + s["gain"]) and s["xirr_pct"] is not None
    lump = c.post("/api/v1/portfolio/simulate", json={"kind": "lump_sum", "target": {"scheme_id": f}, "amount": 100000, "start": "2018-01-01", "end": "2020-12-31"}).json()
    assert lump["final_value"] > 0 and lump["target"]["type"] == "fund"
    roll = c.post("/api/v1/portfolio/simulate", json={"kind": "rolling_sip", "target": {"scheme_id": f}, "monthly": 5000, "horizon_years": 5}).json()
    p = roll["xirr_pct"]
    assert roll["available"] and p["p5"] <= p["median"] <= p["p95"] and "overlap" in roll["note"]
    swp = c.post("/api/v1/portfolio/simulate", json={"kind": "swp", "target": {"holdings": holdings(world["flexi"][:3])}, "corpus": 1e6, "monthly": 8000, "inflation_pct": 5}).json()
    assert swp["target"]["type"] == "portfolio" and swp["total_withdrawn"] > 0 and "depleted" in swp


def test_projections_are_labelled_hypothetical_and_never_pass_for_history(world):
    f = world["flexi"][0]
    c = api()
    p = c.post("/api/v1/portfolio/simulate", json={"kind": "projection", "target": {"scheme_id": f}, "monthly": 10000, "years": 10,
                                                   "annual_return_pct": 11, "annual_volatility_pct": 15}).json()
    assert p["kind"] == "hypothetical" and "not a forecast" in p["label"] and "not a forecast" in p["note"]
    assert p["percentiles"]["p5"] < p["percentiles"]["median"] < p["percentiles"]["p95"] and p["assumptions"]["annual_return_pct"] == 11
    d = c.post("/api/v1/portfolio/simulate", json={"kind": "projection", "target": {"scheme_id": f}, "monthly": 10000, "years": 5}).json()
    assert d["history_for_reference"]["annualised_return_pct"] is not None  # defaults come from history and say so
    b = c.post("/api/v1/portfolio/simulate", json={"kind": "bootstrap", "target": {"scheme_id": f}, "monthly": 10000, "years": 5}).json()
    assert b["kind"] == "hypothetical" and "recombine" in b["note"]


def test_simulate_validation(world):
    c, f = api(), world["flexi"][0]
    for body, msg in [({"kind": "x", "target": {"scheme_id": f}}, "kind must be"), ({"kind": "sip", "target": {"scheme_id": f}, "monthly": 1}, "monthly must be"),
                      ({"kind": "sip", "target": {}, "monthly": 5000}, "target must be"), ({"kind": "sip", "target": {"scheme_id": f}, "monthly": 5000, "start": "1990-01-01"}, "before the data begins"),
                      ({"kind": "projection", "target": {"scheme_id": f}, "years": 99}, "years must be"), ({"kind": "sip", "target": {"scheme_id": world["idcw"][0]}, "monthly": 5000}, "cannot be used")]:
        r = c.post("/api/v1/portfolio/simulate", json=body)
        assert r.status_code == 422 and msg in r.json()["detail"], (body, r.text)


# ------------------------------------------------------------------ rebalance & stress
def test_rebalance_plan_nets_to_new_cash_and_charges_exit_loads_on_recent_units(world):
    a, b, c = world["flexi"][:3]
    body = {"holdings": [{"scheme_id": a, "value": 60000, "held_days": 90}, {"scheme_id": b, "value": 30000, "held_days": 800}, {"scheme_id": c, "value": 10000}],
            "targets": [{"scheme_id": a, "weight": 40}, {"scheme_id": b, "weight": 40}, {"scheme_id": c, "weight": 20}],
            "new_cash": 10000, "cost_pct": 0.1, "exit_load_pct": 1.0, "threshold_pct": 5}
    p = api().post("/api/v1/portfolio/rebalance", json=body).json()
    buys = sum(t["amount"] for t in p["trades"] if t["action"] == "buy")
    sells = sum(t["amount"] for t in p["trades"] if t["action"] == "sell")
    assert buys - sells == pytest.approx(10000) and p["rebalance_triggered"] and p["total_value"] == 110000
    sell = next(t for t in p["trades"] if t["action"] == "sell")
    assert sell["scheme_id"] == a and sell["exit_load"] == pytest.approx(0.01 * sell["amount"]) and sell["name"]
    assert sum(w["target_pct"] for w in p["weights"]) == pytest.approx(100.0) and "tax" in p["note"].lower()
    bad = api().post("/api/v1/portfolio/rebalance", json={**body, "holdings": [{"scheme_id": world["idcw"][0], "value": 1}]})
    assert bad.status_code == 422


def test_stress_uses_episodes_from_the_data_and_marks_unavailable_ones_honestly(world):
    ids = world["flexi"][:3] + world["large"][:2]
    d = api().post("/api/v1/portfolio/stress", json={"holdings": holdings(ids)}).json()
    assert d["historical_episodes"] and "not from an external event list" in d["market_proxy"]
    worst = d["historical_episodes"][0]
    assert worst["fall_pct"] < -5 and worst["available"] and worst["portfolio_change_pct"] < 0  # the planted crash hurts the portfolio
    assert d["hypothetical"]["kind"] == "hypothetical" and d["hypothetical"]["scenarios"][1]["market_shock_pct"] == -20
    assert d["hypothetical"]["beta"] > 0 and "understates" in d["notes"][1]


def test_eligible_fund_search_only_offers_usable_funds(world):
    c = api()
    allf = c.get("/api/v1/portfolio/funds", params={"limit": 50}).json()
    ids = {f["scheme_id"] for f in allf}
    assert world["idcw"][0] not in ids and world["unmapped"] not in ids and all({"name", "category", "plan", "tier"} <= set(f) for f in allf)
    hit = c.get("/api/v1/portfolio/funds", params={"q": allf[0]["name"][:6]}).json()
    assert hit and all(allf[0]["name"][:6].lower() in f["name"].lower() for f in hit)
    assert c.get("/api/v1/portfolio/funds", params={"q": "zzzz-no-such-fund"}).json() == []
    assert c.get("/api/v1/portfolio/funds", params={"limit": 500}).status_code == 422


def test_fund_lookup_by_ids_keeps_order_and_skips_ineligible(world):
    ids = [world["flexi"][2], world["idcw"][0], world["flexi"][0]]
    got = api().get("/api/v1/portfolio/funds", params={"ids": ",".join(map(str, ids))}).json()
    assert [f["scheme_id"] for f in got] == [ids[0], ids[2]]
    assert api().get("/api/v1/portfolio/funds", params={"ids": "a,b"}).status_code == 422


def test_precomputed_category_benchmark_matches_loading_peers(world):
    import numpy as np

    from app.db import session_factory
    from app.services import analytics

    with session_factory()() as s:
        fd = analytics.load_fund(s, world["flexi"][0])
        slow_idx, slow_n, _ = analytics.category_benchmark(s, fd)   # no precomputed file yet: peers are loaded
        assert analytics.build_benchmarks(s) >= 1
        fast_idx, fast_n, _ = analytics.category_benchmark(s, fd)   # now served from sums and counts
        assert analytics._aggregate_for(analytics._group_key(fd.category, fd.plan_type)) is not None
    assert slow_n == fast_n == len(world["flexi"]) - 1 and not slow_idx.empty
    assert (slow_idx.index == fast_idx.index).all() and np.allclose(slow_idx.to_numpy(), fast_idx.to_numpy(), rtol=1e-9)
