from app.services.amc import MIN_CATEGORIES, MIN_FUNDS, summarise
from fastapi.testclient import TestClient


def fund(amc_id, cat, pct, i=[0]):
    i[0] += 1
    return {"scheme_id": i[0], "name": f"f{i[0]}", "amc_id": amc_id, "amc": f"AMC{amc_id}", "category": cat, "p_score": pct, "p_ret": pct, "p_sharpe": pct,
            "composite": pct, "ret_3y": 10.0, "rank": 1, "peers": 10}


def test_median_not_best_fund_and_eligibility_gates():
    cats = ["A", "B", "C"]
    star = [fund(1, c, p) for c, p in zip(cats * 2, [100, 100, 100, 10, 10, 10])]  # one star per category, weak otherwise
    steady = [fund(2, c, 60) for c in cats * 2]
    small = [fund(3, "A", 99) for _ in range(MIN_FUNDS)]  # enough funds, one category
    few = [fund(4, c, 90) for c in cats]  # enough categories, too few funds
    out = {r["amc_id"]: r for r in summarise(star + steady + small + few)}
    assert out[2]["rank"] == 1 and out[1]["rank"] == 2          # steady beats star-driven
    assert out[1]["median_score_percentile"] == 55.0 and out[2]["median_score_percentile"] == 60.0
    for k in (3, 4):
        assert out[k]["rank"] is None and not out[k]["eligible"] and "needs at least" in out[k]["reason"] and out[k]["median_score_percentile"] is None
    assert out[3]["largest_category_share"] == 100.0 and out[3]["concentration_hhi"] == 1.0
    assert MIN_CATEGORIES == 3


def test_unscored_funds_are_excluded_not_zeroed():
    fs = [fund(7, c, 80) for c in "ABCDE"] + [fund(7, "A", None)]
    r = summarise(fs)[0]
    assert r["funds"] == 6 and r["scored_funds"] == 5 and r["median_score_percentile"] == 80.0


def test_amc_api_shape(loaded):
    from app.main import app

    c = TestClient(app)
    d = c.get("/api/v1/amcs").json()
    assert d["amcs"] and d["method"] and d["version"]
    ranks = [a["rank"] for a in d["amcs"] if a["eligible"]]
    assert ranks == list(range(1, len(ranks) + 1))
    first = d["amcs"][0]
    det = c.get(f"/api/v1/amcs/{first['amc_id']}").json()
    assert det["summary"]["amc"] == first["amc"] and det["funds"] and det["categories"]
    assert c.get("/api/v1/amcs/99999999").status_code == 404
