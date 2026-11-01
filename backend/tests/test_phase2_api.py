import pytest
from app.api.screener import _safe
from sqlalchemy import text


def client():
    from app.main import app
    from fastapi.testclient import TestClient

    return TestClient(app)


def screen(body):
    return client().post("/api/v1/screener", json=body)


def cond(field, op, value=None):
    return {"field": field, "op": op, "value": value}


# ---------- overview ----------
def test_overview_universe_and_counts(loaded):
    d = client().get("/api/v1/overview").json()
    c = d["counts"]
    assert c["schemes_total"] == 3351 and c["insurer_funds"] == 305 and c["discontinued"] == 8
    assert c["schemes_in_universe"] == 3038  # excludes insurer + discontinued (overlap handled by SQL)
    assert sum(t["schemes"] for t in d["tiers"]) == c["schemes_in_universe"]


def test_overview_include_insurer_changes_universe(loaded):
    d = client().get("/api/v1/overview", params={"include_insurer": True}).json()
    assert d["counts"]["schemes_in_universe"] > 3038


def test_overview_aum_is_family_level_with_coverage(loaded, session):
    d = client().get("/api/v1/overview").json()["aum"]
    assert 0 < d["coverage"] < 1 and d["families_with_aum"] < d["families_total"]
    # independent check: max net assets per family, summed
    expected = session.execute(text("""
        select sum(m) from (
          select max(f.net_assets) m from fund_snapshots f join schemes s on s.id=f.scheme_id
          where f.ingestion_run_id = (select max(id) from ingestion_runs where status='succeeded') and s.is_insurer_fund=false and s.is_discontinued=false and f.quarantined=false
            and s.family_id is not null and f.net_assets is not null
          group by s.family_id) t""")).scalar()
    assert d["total_rupees"] == pytest.approx(expected)


def test_overview_breadth_in_unit_interval(loaded):
    for row in client().get("/api/v1/overview").json()["breadth"]:
        for v in row["positive_return_share"].values():
            assert 0 <= v <= 1
        assert 0 <= row["above_200d_avg"] <= 1


def test_overview_amc_leaderboard_respects_min_sample(loaded):
    lb = client().get("/api/v1/overview").json()["amc_leaderboard"]
    assert all(r["schemes_with_3y"] >= lb["min_schemes"] for r in lb["rows"])
    pcts = [r["median_3y_category_percentile"] for r in lb["rows"]]
    assert pcts == sorted(pcts, reverse=True)


def test_overview_top_performers_one_per_family_and_bad_horizon(loaded):
    d = client().get("/api/v1/overview", params={"horizon": "3y"}).json()["top_performers"]
    rets = [r["ret"] for r in d["rows"]]
    assert rets == sorted(rets, reverse=True) and d["horizon"] == "3y"
    assert client().get("/api/v1/overview", params={"horizon": "10y"}).status_code == 422


# ---------- screener ----------
def test_screener_and_matches_independent_sql(loaded, session):
    body = {"filter": {"op": "and", "items": [cond("category", "eq", "Flexi Cap"), cond("plan_type", "eq", "Direct"),
                                               cond("option_type", "eq", "Growth")]}}
    got = screen(body).json()["total"]
    exp = session.execute(text("""select count(*) from schemes s join fund_categories c on c.id=s.category_id
        where c.name='Flexi Cap' and s.plan_type='Direct' and s.option_type='Growth'""")).scalar()
    assert got == exp > 0


def test_screener_or(loaded):
    a = screen({"filter": {"items": [cond("category", "eq", "Flexi Cap")]}}).json()["total"]
    b = screen({"filter": {"items": [cond("category", "eq", "ELSS (Tax Savings)")]}}).json()["total"]
    both = screen({"filter": {"op": "or", "items": [cond("category", "eq", "Flexi Cap"),
                                                      cond("category", "eq", "ELSS (Tax Savings)")]}}).json()["total"]
    assert both == a + b


def test_screener_nulls_never_match_numeric_conditions(loaded, session):
    got = screen({"filter": {"items": [cond("net_assets", "gt", 0)]}}).json()["total"]
    nonnull = session.execute(text("select count(*) from fund_snapshots f where net_assets > 0 and "+"f.ingestion_run_id = (select max(id) from ingestion_runs where status='succeeded')")).scalar()
    assert got == nonnull and got < 3351
    isnull = screen({"filter": {"items": [cond("net_assets", "is_null")]}}).json()["total"]
    assert isnull == 1067


def test_screener_percentile_scale_is_percent(loaded):
    r = screen({"filter": {"items": [cond("cat_pct_3y", "gt", 99)]}}).json()
    assert r["total"] > 0 and all(i["cat_pct_3y"] > 99 for i in r["items"]) and all(i["cat_pct_3y"] <= 100 for i in r["items"])


def test_screener_between_and_in(loaded):
    r = screen({"filter": {"items": [cond("return_1y", "between", [10, 12]), cond("asset_tier", "in", ["Equity", "Hybrid"])]}}).json()
    assert r["total"] > 0 and all(10 <= i["return_1y"] <= 12 and i["asset_tier"] in ("Equity", "Hybrid") for i in r["items"])


def test_screener_empty_groups(loaded):
    assert screen({"filter": {"op": "and", "items": []}}).json()["total"] == 3351
    assert screen({"filter": {"op": "or", "items": []}}).json()["total"] == 0


@pytest.mark.parametrize(
    "body",
    [
        {"filter": {"items": [cond("price; drop table schemes", "gt", 1)]}},
        {"filter": {"items": [cond("price", "like", 1)]}},
        {"filter": {"items": [cond("category", "gt", "x")]}},
        {"filter": {"items": [cond("price", "gt", "abc")]}},
        {"filter": {"items": [cond("price", "between", [1])]}},
        {"filter": {}, "sort": "price; --"},
        {"filter": {}, "sort": "amc"},
        {"filter": {}, "page_size": 5000},
    ],
)
def test_screener_rejects_invalid_requests(loaded, body):
    assert screen(body).status_code == 422


def test_screener_rejects_deep_and_huge_trees(loaded):
    node = {"op": "and", "items": [cond("price", "gt", 1)]}
    for _ in range(4):
        node = {"op": "and", "items": [node]}
    assert screen({"filter": node}).status_code == 422
    big = {"op": "and", "items": [cond("price", "gt", 1)] * 30}
    assert screen({"filter": big}).status_code == 422


def test_screener_sort_desc_nulls_last_and_paging(loaded):
    p1 = screen({"filter": {}, "sort": "return_5y", "order": "desc", "page_size": 5}).json()
    vals = [i["return_5y"] for i in p1["items"]]
    assert vals == sorted(vals, reverse=True) and None not in vals
    p2 = screen({"filter": {}, "sort": "return_5y", "order": "desc", "page_size": 5, "page": 2}).json()
    assert {i["id"] for i in p1["items"]}.isdisjoint({i["id"] for i in p2["items"]})


def test_screener_fields_catalog(loaded):
    f = client().get("/api/v1/screener/fields").json()
    assert {"cat_pct_3y", "category", "net_assets"} <= {x["key"] for x in f}


def test_export_csv_and_formula_sanitising(loaded):
    r = client().post("/api/v1/screener/export", json={"filter": {"items": [cond("asset_tier", "eq", "Equity")]}})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    lines = r.text.strip().splitlines()
    assert len(lines) == 1 + 1276 and r.headers["x-truncated"] == "false"
    assert _safe("=cmd()") == "'=cmd()" and _safe("@x") == "'@x" and _safe(-1.5) == -1.5 and _safe(None) == ""


# ---------- compare / filters ----------
def test_compare_limits_and_warnings(loaded):
    c = client()
    assert c.get("/api/v1/compare", params={"ids": "1,2,3,4,5,6"}).status_code == 422
    assert c.get("/api/v1/compare", params={"ids": "a,b"}).status_code == 422
    assert c.get("/api/v1/compare", params={"ids": "1,99999999"}).status_code == 404
    d = c.get("/api/v1/compare", params={"ids": "1,2"}).json()
    assert [f["id"] for f in d["funds"]] == [1, 2] and all("cat_pct_1y" in f["metrics"] for f in d["funds"])


def test_compare_same_category_has_no_category_warning(loaded):
    ids = [i["id"] for i in screen({"filter": {"items": [cond("category", "eq", "Flexi Cap"), cond("plan_type", "eq", "Direct"),
                                                          cond("option_type", "eq", "Growth")]}}).json()["items"][:3]]
    d = client().get("/api/v1/compare", params={"ids": ",".join(map(str, ids))}).json()
    assert not any("different categories" in w for w in d["warnings"])


def test_filter_options(loaded):
    d = client().get("/api/v1/filters/options").json()
    assert len(d["amcs"]) == 55 and len(d["categories"]) == 49
    assert sum(x["count"] for x in d["asset_tiers"]) == 3351
