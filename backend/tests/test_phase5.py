"""Phase 5 end to end on a synthetic universe: build -> scores -> research -> backtest jobs."""
import os
import time

import numpy as np
import pandas as pd
import pytest
from app.core.config import get_settings
from app.models import AmfiScheme, FundScore, Scheme, SchemeMapping
from app.services import analytics, quant
from data_pipeline.nav.store import NavStore
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text


@pytest.fixture(scope="module")
def built(migrated, loaded, tmp_path_factory):
    from app.db import session_factory

    tmp = tmp_path_factory.mktemp("phase5")
    old = os.environ.get("QSMF_DATA_DIR")
    os.environ["QSMF_DATA_DIR"] = str(tmp)
    get_settings.cache_clear()
    analytics._rf_cached.cache_clear()
    quant._bundle_cache.clear()
    with session_factory()() as s:
        for t in ("fund_scores", "backtest_runs", "scheme_metrics", "scheme_mappings", "nav_coverage", "amfi_schemes"):
            s.execute(text(f"delete from {t}"))
        s.commit()
        funds = list(s.scalars(select(Scheme).join(Scheme.category).where(Scheme.plan_type == "Direct", Scheme.option_type == "Growth", Scheme.is_insurer_fund.is_(False))
                               .where(text("fund_categories.name = 'Flexi Cap'")).order_by(Scheme.id).limit(14)))
        store = NavStore(tmp / "silver" / "nav")
        idx = pd.bdate_range("2014-01-01", "2026-10-30")
        rng = np.random.default_rng(11)
        market = rng.normal(0.0004, 0.008, len(idx))
        drift = rng.normal(0, 0.0003, len(funds))
        for i, f in enumerate(funds):
            code = str(910000 + i)
            nav = 100 * np.cumprod(1 + drift[i] + 0.8 * market + rng.normal(0, 0.005, len(idx)))
            s.add(AmfiScheme(code=code, name=f.name, amc="x", latest_nav=float(nav[-1])))
            s.flush()
            s.add(SchemeMapping(scheme_id=f.id, amfi_code=code, variant="growth", status="confirmed", method="t", matcher_version="t"))
            store.upsert((code, d.date(), float(v), "t") for d, v in zip(idx, nav))
        s.commit()
        out = quant.build_all(s, step=3)
    yield {"funds": funds, "build": out, "dir": tmp}
    if old is None:
        os.environ.pop("QSMF_DATA_DIR", None)
    else:
        os.environ["QSMF_DATA_DIR"] = old
    get_settings.cache_clear()
    quant._bundle_cache.clear()


def client():
    from app.main import app

    return TestClient(app)


def test_build_stores_scores_history_and_research_files(built, migrated):
    from app.db import session_factory

    assert built["build"]["funds"] == 14 and built["build"]["dates"] > 30 and built["build"]["scored_latest"] == 14
    for f in ("score_history.parquet", "factors.json", "clusters.json", "regimes.json"):
        assert (built["dir"] / "gold" / "quant" / f).exists()
    with session_factory()() as s:
        assert s.scalar(select(func.count()).select_from(FundScore)) == 14
        row = s.scalars(select(FundScore)).first()
        assert len(row.detail["metrics"]) == 17 and row.methodology_version == "score-1.0.0" and row.as_of.year == 2026


def test_methodology_endpoint_states_the_unavailable_stability_factor(built):
    m = client().get("/api/v1/quant/methodology").json()
    assert m["weights"]["stability"] == 5.0 and "stability" in m["unavailable"] and sum(m["weights"].values()) == 100
    assert {"multi_factor", "momentum_12m", "regime_aware"} <= set(m["strategies"])


def test_scores_list_filters_sorts_and_validates(built):
    c = client()
    r = c.get("/api/v1/quant/scores", params={"group": "Flexi Cap | Direct", "page_size": 5}).json()
    assert r["total"] == 14 and len(r["items"]) == 5 and r["methodology_version"] == "score-1.0.0"
    vals = [i["composite"] for i in r["items"]]
    assert vals == sorted(vals, reverse=True) and [i["rank_in_group"] for i in r["items"]] == [1, 2, 3, 4, 5]
    assert c.get("/api/v1/quant/scores", params={"q": "zzzz-nothing"}).json()["total"] == 0
    assert c.get("/api/v1/quant/scores", params={"sort": "drop table"}).status_code == 422


def test_score_detail_breakdown_is_internally_consistent(built):
    sid = client().get("/api/v1/quant/scores", params={"page_size": 1}).json()["items"][0]["scheme_id"]
    d = client().get(f"/api/v1/quant/scores/{sid}").json()
    assert d["available"] and d["scored"] and len(d["metrics"]) == 16
    assert [f["key"] for f in d["factors"]][-1] == "stability" and d["factors"][-1]["score"] is None
    assert sum(f["contribution"] or 0 for f in d["factors"]) == pytest.approx(d["composite"])
    assert 0 < d["coverage"] <= 0.95 and "not a prediction" in d["caveat"]
    assert all(0 <= (m["percentile"] or 0) <= 100 for m in d["metrics"])


def test_unscored_and_unknown_funds_are_handled(built):
    from app.db import session_factory

    with session_factory()() as s:
        other = s.scalars(select(Scheme).where(Scheme.id.notin_([f.id for f in built["funds"]])).limit(1)).one()
    d = client().get(f"/api/v1/quant/scores/{other.id}").json()
    assert d["available"] is False and "Growth schemes" in d["reason"]
    assert client().get("/api/v1/quant/scores/99999999").status_code == 404


def test_research_outputs_carry_caveats_and_no_meaningless_statistics(built):
    c = client()
    f = c.get("/api/v1/quant/factors").json()
    assert f["ic"] == []  # 14 funds: below the 20-fund minimum for a cross-sectional rank correlation, so nothing is invented
    assert any("Survivorship" in x for x in f["caveats"]) and f["persistence"]["random_expectation"] == 0.25
    assert all(r["t_stat"] is None or r["independent_dates"] >= 10 for r in f["ic"])
    s = c.get("/api/v1/quant/statistics").json()
    assert s["correlations"]["matrix"] == [] and s["distributions"] == []  # needs >= 30 / >= 20 funds; 14 here, so empty, not invented
    cl = c.get("/api/v1/quant/clusters").json()["clusters"]
    assert cl["Equity"]["available"] is False and "fewer than" in cl["Equity"]["reason"]  # 14 funds: too few to cluster honestly
    rg = c.get("/api/v1/quant/regimes").json()
    assert rg["hmm"]["train_end"] and "forward-only" in rg["hmm"]["note"] and rg["gmm"]["hindsight"] is True
    assert {s["regime"] for s in rg["trend"]["stats"]} <= {"bull", "bear", "sideways"}


def _wait(c, rid, seconds=120):
    t0 = time.time()
    while time.time() - t0 < seconds:
        j = c.get(f"/api/v1/jobs/{rid}").json()
        if j["status"] in ("succeeded", "failed"):
            return j
        time.sleep(0.5)
    raise AssertionError("backtest did not finish")


def test_backtest_job_lifecycle_caching_and_provenance(built):
    c = client()
    req = {"strategy": "multi_factor", "top_n": 5, "rebalance_months": 3, "universe": {"tier": "Equity", "plan": "Direct"}}
    r = c.post("/api/v1/quant/backtests", json=req)
    assert r.status_code == 202 and r.json()["poll"].startswith("/api/v1/jobs/")
    rid = r.json()["id"]
    assert _wait(c, rid)["status"] == "succeeded"
    res = c.get(f"/api/v1/quant/backtests/{rid}").json()
    assert res["available"] and res["universe"]["funds"] == 14 and res["backtest_version"] == "backtest-1.0.0"
    assert any("Survivorship" in w for w in res["warnings"]) and res["in_sample"] and res["out_of_sample"]
    assert res["costs"]["avg_holdings"] == pytest.approx(5.0)
    again = c.post("/api/v1/quant/backtests", json=req)
    assert again.json()["id"] == rid  # identical request + identical data = cached run, not recomputed


def test_backtest_validation_and_failure_reporting(built):
    c = client()
    bad = [{"strategy": "crystal_ball"}, {"strategy": "multi_factor", "top_n": 500}, {"strategy": "multi_factor", "cost_pct": 50},
           {"strategy": "multi_factor", "universe": {"tier": "Space"}}, {"strategy": "multi_factor", "start": "not-a-date"}]
    for b in bad:
        assert c.post("/api/v1/quant/backtests", json=b).status_code == 422, b
    r = c.post("/api/v1/quant/backtests", json={"strategy": "momentum_12m", "universe": {"tier": "Debt"}})  # no debt funds in this test world
    j = _wait(c, r.json()["id"])
    assert j["status"] == "failed" and "at least 10" in j["error"]
    assert c.get(f"/api/v1/quant/backtests/{r.json()['id']}").status_code == 409
    assert c.get("/api/v1/quant/backtests/99999999").status_code == 404 and c.get("/api/v1/jobs/99999999").status_code == 404


def test_regime_aware_without_a_defensive_universe_still_runs_or_explains(built):
    c = client()
    r = c.post("/api/v1/quant/backtests", json={"strategy": "regime_aware", "top_n": 5, "universe": {"tier": "Equity"}})
    j = _wait(c, r.json()["id"])
    assert j["status"] in ("succeeded", "failed")
    if j["status"] == "succeeded":
        assert c.get(f"/api/v1/quant/backtests/{r.json()['id']}").json()["config"]["strategy"] == "regime_aware"


def test_screener_filters_and_sorts_on_the_quant_score(built):
    c = client()
    body = {"filter": {"items": [{"field": "quant_score", "op": "gt", "value": 0}]}, "sort": "quant_score", "order": "desc", "page_size": 50}
    r = c.post("/api/v1/screener", json=body).json()
    assert r["total"] == 14  # only the 14 scored funds match; every other scheme has no score and never matches
    vals = [i["quant_score"] for i in r["items"]]
    assert vals == sorted(vals, reverse=True) and all(0 <= v <= 100 for v in vals)
    top = c.post("/api/v1/screener", json={"filter": {"items": [{"field": "quant_f_momentum", "op": "gte", "value": 90}]}}).json()
    assert 0 < top["total"] < 14
    assert {"quant_score", "quant_rank", "quant_f_downside"} <= {f["key"] for f in c.get("/api/v1/screener/fields").json()}


def test_new_backtests_can_be_switched_off_but_cached_ones_still_serve(built, monkeypatch):
    from app.core.config import get_settings

    c = client()
    cached = {"strategy": "multi_factor", "top_n": 5, "rebalance_months": 3, "universe": {"tier": "Equity", "plan": "Direct"}}
    new = {"strategy": "momentum_6m", "top_n": 7, "rebalance_months": 6, "universe": {"tier": "Equity", "plan": "Direct"}}
    monkeypatch.setenv("QSMF_ENABLE_BACKTESTS", "false")
    get_settings.cache_clear()
    try:
        r = c.post("/api/v1/quant/backtests", json=new)
        assert r.status_code == 503 and "switched off" in r.json()["detail"]
        assert c.post("/api/v1/quant/backtests", json=cached).status_code == 202  # an identical earlier run is returned, not recomputed
    finally:
        monkeypatch.delenv("QSMF_ENABLE_BACKTESTS")
        get_settings.cache_clear()
