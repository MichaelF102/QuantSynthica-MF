"""Reports must carry exactly the numbers the API serves."""
import io

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from tests.test_phase6 import world  # noqa: F401  (synthetic NAV universe in the throwaway test database)


class _Client:
    """Created on first use, after the test database URL is in place (importing app.main earlier would bind the dev database)."""

    _c = None

    def __getattr__(self, name):
        if _Client._c is None:
            from app.main import app

            _Client._c = TestClient(app)
        return getattr(_Client._c, name)


c = _Client()


def sheet_rows(content: bytes, prefix: str):
    wb = load_workbook(io.BytesIO(content))
    ws = next(w for w in wb.worksheets if w.title.split(". ", 1)[-1].startswith(prefix))
    rows = []
    for r in ws.iter_rows(min_row=3, values_only=True):
        if not any(x is not None for x in r):
            break  # a blank row ends the table; the footnote follows it
        rows.append(list(r))
    return rows


@pytest.fixture(scope="module")
def fund_id(world):  # noqa: F811
    return world["flexi"][0]


def test_fund_xlsx_numbers_match_the_api(fund_id):
    api = c.get(f"/api/v1/analytics/{fund_id}", params={"years": "3"}).json()
    r = c.post("/api/v1/reports/fund.xlsx", json={"scheme_id": fund_id, "years": 3})
    assert r.status_code == 200 and "spreadsheetml" in r.headers["content-type"]
    rows = sheet_rows(r.content, "Trailing returns")
    got = {row[0]: row[1] for row in rows}
    for k, m in api["trailing_returns"].items():
        assert got[k.upper()] == pytest.approx(m["value"], rel=1e-12)  # Excel stores 15 significant digits
    cal = {row[0]: row[1] for row in sheet_rows(r.content, "Calendar-year")}
    for y in api["calendar_returns"]:
        assert cal[y["year"]] == pytest.approx(y["return"], rel=1e-12)
    win = {row[0]: row for row in sheet_rows(r.content, "Risk and return")}
    for w in api["windows"]:
        if w["available"]:
            assert win[f"{w['years']}Y"][1] == pytest.approx(w["cagr"]["value"], rel=1e-12) and win[f"{w['years']}Y"][5] == pytest.approx(w["max_drawdown"]["value"], rel=1e-12)


def test_amc_xlsx_matches_ranking_and_pdf_is_a_pdf(fund_id):  # noqa: F811
    api = c.get("/api/v1/amcs").json()
    rows = sheet_rows(c.post("/api/v1/reports/amc.xlsx", json={}).content, "Fund houses")
    assert [r[1] for r in rows] == [a["amc"] for a in api["amcs"]]
    assert [r[0] for r in rows] == [a["rank"] for a in api["amcs"]]
    assert [r[5] for r in rows] == [pytest.approx(a["median_score_percentile"], rel=1e-12) if a["median_score_percentile"] is not None else None for a in api["amcs"]]
    pdf = c.post("/api/v1/reports/amc.pdf", json={})
    assert pdf.status_code == 200 and pdf.content[:5] == b"%PDF-" and len(pdf.content) > 2000
    f = c.post("/api/v1/reports/fund.pdf", json={"scheme_id": fund_id})
    assert f.content[:5] == b"%PDF-"


def test_portfolio_report_matches_analysis(world):  # noqa: F811
    h = [{"scheme_id": i, "weight": 1} for i in world["flexi"][:3]]
    api = c.post("/api/v1/portfolio/analyze", json={"holdings": h, "years": 3}).json()
    rows = sheet_rows(c.post("/api/v1/reports/portfolio.xlsx", json={"holdings": h}).content, "Holdings")
    assert [r[3] for r in rows] == pytest.approx([f["weight_pct"] for f in api["funds"]], rel=1e-12)
    if api.get("risk"):
        assert [r[4] for r in rows] == pytest.approx(api["risk"]["risk_contribution_pct"], rel=1e-12)


def test_report_errors_and_disclaimer():
    assert c.post("/api/v1/reports/fund.xlsx", json={}).status_code == 422
    assert c.post("/api/v1/reports/nope.xlsx", json={}).status_code == 422
    assert c.post("/api/v1/reports/amc.docx", json={}).status_code == 422
    assert c.post("/api/v1/reports/portfolio.pdf", json={"holdings": []}).status_code == 422
    wb = load_workbook(io.BytesIO(c.post("/api/v1/reports/amc.xlsx", json={}).content))
    assert any("not investment advice" in str(r[0]) for r in wb["Summary"].iter_rows(values_only=True))
