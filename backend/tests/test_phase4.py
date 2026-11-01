"""Phase 4: analytics service, API and batch metrics, on synthetic NAV for a few real CSV schemes."""

import numpy as np
import pandas as pd
import pytest
from app.core.config import get_settings
from app.models import AmfiScheme, Scheme, SchemeMapping, SchemeMetric
from app.services import analytics
from data_pipeline.nav.store import NavStore
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text


@pytest.fixture()
def world(session, loaded, tmp_path, monkeypatch):
    """Eight Flexi Cap Direct-Growth schemes with synthetic NAV, plus one broken-NAV fund, an IDCW fund and an unmapped fund."""
    monkeypatch.setenv("QSMF_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    analytics._rf_cached.cache_clear()
    analytics._bench_cached.cache_clear()
    for t in ("scheme_metrics", "scheme_mappings", "nav_coverage", "amfi_schemes"):
        session.execute(text(f"delete from {t}"))
    session.commit()

    q = (select(Scheme).join(Scheme.category).where(Scheme.plan_type == "Direct", Scheme.option_type == "Growth", Scheme.is_insurer_fund.is_(False))
         .where(text("fund_categories.name = 'Flexi Cap'")).order_by(Scheme.id).limit(9))
    growth = list(session.scalars(q))
    idcw = session.scalars(select(Scheme).where(Scheme.option_type == "IDCW", Scheme.is_insurer_fund.is_(False)).limit(1)).one()
    unmapped = session.scalars(select(Scheme).where(Scheme.option_type == "Growth", Scheme.is_insurer_fund.is_(False),
                                                    Scheme.id.notin_([g.id for g in growth])).limit(1)).one()
    store = NavStore(tmp_path / "silver" / "nav")
    idx = pd.bdate_range("2019-01-01", "2026-10-30")
    rng = np.random.default_rng(42)
    market = rng.normal(0.0004, 0.009, len(idx))
    codes = {}
    for i, sch in enumerate(growth + [idcw]):
        code = str(900000 + i)
        codes[sch.id] = code
        r = 0.0001 * i + 0.8 * market + rng.normal(0, 0.004, len(idx))
        nav = 100 * np.cumprod(1 + r)
        if i == 8:  # the broken one: a -90% unit-consolidation step in the last year
            nav[-120:] = nav[-120:] / 10
        session.add(AmfiScheme(code=code, name=sch.name, amc="x", latest_nav=float(nav[-1])))
        session.flush()
        status = "confirmed"
        session.add(SchemeMapping(scheme_id=sch.id, amfi_code=code, variant="growth" if sch.option_type == "Growth" else "idcw_payout",
                                  status=status, method="t", matcher_version="t"))
        store.upsert((code, d.date(), float(v), "t") for d, v in zip(idx, nav))
    session.add(SchemeMapping(scheme_id=unmapped.id, amfi_code=None, status="unmapped", method="t", matcher_version="t"))
    session.commit()
    yield {"growth": growth, "idcw": idcw, "unmapped": unmapped, "codes": codes}
    get_settings.cache_clear()


def client():
    from app.main import app

    return TestClient(app)


def test_fund_analytics_has_every_metric_with_provenance(world):
    g = world["growth"][0]
    d = client().get(f"/api/v1/analytics/{g.id}?years=3").json()
    assert d["available"] and d["methodology_version"] == "perf-risk-1.0.0"
    assert d["peer_count"] == 7  # eight healthy peers minus the fund itself; the broken fund is excluded from the index
    assert "survivi" in d["benchmark_label"] and "equal-weighted" in d["benchmark_label"]
    w3 = next(w for w in d["windows"] if w["years"] == 3)
    for k in ("cagr", "volatility", "sharpe_ratio", "sortino_ratio", "max_drawdown", "calmar_ratio", "var_95", "cvar_95"):
        assert w3[k]["value"] is not None and w3[k]["n_obs"] > 600 and w3[k]["window_end"] == "2026-10-30"
    assert w3["benchmark"]["beta"]["value"] == pytest.approx(1.0, abs=0.5) and w3["benchmark"]["tracking_error"]["value"] > 0
    assert d["trailing_returns"]["10y"]["value"] is None and d["trailing_returns"]["5y"]["value"] is not None
    assert len(d["calendar_returns"]) >= 7 and d["charts"]["cumulative"]["fund"][0][1] == 100.0
    assert d["charts"]["cumulative"]["category_average"] and d["charts"]["nav_chart"]["dma_200"]


def test_unavailable_cases_give_honest_reasons(world):
    c = client()
    assert "IDCW" in c.get(f"/api/v1/analytics/{world['idcw'].id}").json()["reason"]
    d = c.get(f"/api/v1/analytics/{world['unmapped'].id}").json()
    assert d["available"] is False and "link" in d["reason"].lower()
    assert c.get("/api/v1/analytics/99999999").status_code == 404
    assert c.get("/api/v1/analytics/1?years=abc").status_code == 422
    assert c.get("/api/v1/analytics/1?years=99").status_code == 422


def test_suspect_nav_jump_makes_affected_windows_unavailable(world):
    broken = world["growth"][8]
    d = client().get(f"/api/v1/analytics/{broken.id}").json()
    assert d["available"] and d["data_issues"] and d["data_issues"][0]["move_pct"] < -80
    assert all(w["available"] is False and w["data_issue"] for w in d["windows"])
    assert d["trailing_returns"]["1y"]["value"] is None and "NAV move" in d["trailing_returns"]["1y"]["note"]
    assert d["trailing_returns"]["5y"]["value"] is None


def test_compare_endpoint_correlation_and_limits(world):
    ids = [g.id for g in world["growth"][:3]]
    c = client()
    d = c.get("/api/v1/analytics/compare", params={"ids": ",".join(map(str, ids)), "years": "3"}).json()
    assert [f["scheme_id"] for f in d["funds"]] == ids
    m = np.array(d["correlation"]["matrix"])
    assert m.shape == (3, 3) and np.allclose(np.diag(m), 1.0) and np.allclose(m, m.T) and (m > 0.5).all()
    assert d["chart"]["available"] and set(d["chart"]["cumulative"]) == {str(i) for i in ids}
    assert c.get("/api/v1/analytics/compare", params={"ids": "1,2,3,4,5,6"}).status_code == 422
    assert c.get("/api/v1/analytics/compare", params={"ids": "x"}).status_code == 422


def test_batch_metrics_cover_only_eligible_schemes_and_rank_within_peers(world, session):
    from app.services.metrics_batch import compute_all

    out = compute_all(session)
    assert out["schemes"] == 9  # eight healthy + the broken one; IDCW and unmapped are not eligible
    ids = set(session.scalars(select(SchemeMetric.scheme_id)))
    assert world["idcw"].id not in ids and world["unmapped"].id not in ids
    rows = {m.scheme_id: m for m in session.scalars(select(SchemeMetric))}
    healthy = [rows[g.id] for g in world["growth"][:8]]
    assert all(0 <= m.pctile_sharpe_3y <= 100 for m in healthy)
    best = max(healthy, key=lambda m: m.sharpe_3y)
    assert best.pctile_sharpe_3y == pytest.approx(100.0)  # highest Sharpe in the peer group ranks first
    low_vol = min(healthy, key=lambda m: m.vol_3y)
    assert low_vol.pctile_vol_3y == pytest.approx(100.0)  # lower volatility is better
    broken = rows[world["growth"][8].id]
    assert broken.sharpe_3y is None and broken.max_dd_3y is None  # data issue: nothing reported

    compute_all(session)  # rerun replaces, does not duplicate
    assert session.scalar(select(func.count()).select_from(SchemeMetric)) == 9


def test_screener_can_filter_and_sort_on_nav_metrics(world, session):
    from app.services.metrics_batch import compute_all

    compute_all(session)
    c = client()
    body = {"filter": {"items": [{"field": "sharpe_3y", "op": "gt", "value": -100}]}, "sort": "sharpe_3y", "order": "desc", "page_size": 50}
    r = c.post("/api/v1/screener", json=body).json()
    assert r["total"] == 8  # only schemes that have a Sharpe; the broken fund and all others never match
    vals = [i["sharpe_3y"] for i in r["items"]]
    assert vals == sorted(vals, reverse=True) and all(i["vol_3y"] is not None for i in r["items"])
    top = c.post("/api/v1/screener", json={"filter": {"items": [{"field": "peer_pct_sharpe_3y", "op": "gte", "value": 100}]}}).json()
    assert top["total"] == 1
    assert {"sharpe_3y", "max_dd_3y", "peer_pct_sharpe_3y"} <= {f["key"] for f in c.get("/api/v1/screener/fields").json()}


def test_fund_detail_prefers_nav_derived_returns_when_available(world, session):
    from app.services.metrics_batch import compute_all

    g = world["growth"][0]
    assert client().get(f"/api/v1/funds/{g.id}").json()["nav_metrics"] is None  # nothing computed yet: UI falls back to source values
    compute_all(session)
    d = client().get(f"/api/v1/funds/{g.id}").json()
    m = session.get(SchemeMetric, g.id)
    assert d["nav_metrics"]["ret_3y"] == pytest.approx(m.ret_3y) and d["nav_metrics"]["as_of"] == "2026-10-30"
    assert d["nav_metrics"]["methodology_version"] == "perf-risk-1.0.0"
