import json
from datetime import date

import pytest
from data_pipeline.http import FetchError, fetch
from data_pipeline.sources import amfi, mfapi

NAV_ALL = """Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Plan;Option;Net Asset Value;Date
 
Open Ended Schemes(Children’s Fund - Childrens' Fund)
 
Axis Mutual Fund
 
135762;INF846K01WO1;-;Axis Children's Fund;Direct Plan;Growth Option;29.1949;30-Oct-2026
135763;INF846K01WS2;INF846K01WQ6;Axis Children's Fund;Direct Plan;IDCW Option;26.9446;30-Oct-2026
bad;row;;;;;;
135999;-;-;Broken NAV Fund;;;N.A.;30-Oct-2026
"""

HISTORY = """Scheme Code;NAV Name;Plan;Option;ISIN Div Payout/ISIN Growth;ISIN Div Reinvestment;Net Asset Value;Date

Open Ended Schemes ( Equity Scheme - Multi Cap Fund )


Aditya Birla Sun Life Mutual Fund
148921;Aditya Birla Sun Life Multi-Cap Fund-Direct Growth;Direct Plan;GROWTH;INF209KB1Y49;;22.04;01-Oct-2026
148920;Aditya Birla Sun Life Multi-Cap Fund-Direct IDCW Payout;Direct Plan;IDCW Payout;INF209KB1Y56;;18.14;05-Oct-2026
"""


def test_parse_latest_nav_file_reads_columns_from_header():
    recs = list(amfi.parse(NAV_ALL))
    assert [r.code for r in recs] == ["135762", "135763", "135999"]
    a, b, c = recs
    assert a.amc == "Axis Mutual Fund" and a.category.startswith("Children")
    assert a.isin_primary == "INF846K01WO1" and a.isin_reinvest is None  # "-" means none
    assert b.isin_reinvest == "INF846K01WQ6"
    assert a.nav == 29.1949 and a.nav_date == date(2026, 10, 30)
    assert c.nav is None  # "N.A." is missing, not zero


def test_parse_history_file_with_different_column_order():
    recs = list(amfi.parse(HISTORY))
    assert recs[0].name.startswith("Aditya Birla") and recs[0].plan == "Direct Plan" and recs[0].option == "GROWTH"
    assert recs[0].isin_primary == "INF209KB1Y49" and recs[0].nav == 22.04 and recs[0].nav_date == date(2026, 10, 1)
    assert recs[1].amc == "Aditya Birla Sun Life Mutual Fund" and recs[1].category == "Equity Scheme - Multi Cap Fund"


def test_html_instead_of_data_is_rejected():
    with pytest.raises(ValueError):
        list(amfi.parse("<!DOCTYPE html><html>error</html>\n;"))
    with pytest.raises(ValueError):
        amfi._validate_text(b"<!DOCTYPE html><html></html>")


def test_history_windows_respect_the_90_day_limit_and_cover_the_range():
    wins = list(amfi.history_windows(date(2026, 1, 1), date(2026, 12, 31)))
    assert all((b - a).days + 1 <= 90 for a, b in wins)
    assert wins[0][0] == date(2026, 1, 1) and wins[-1][1] == date(2026, 12, 31)
    assert all(wins[i][1] + (date(2026, 1, 2) - date(2026, 1, 1)) == wins[i + 1][0] for i in range(len(wins) - 1))
    with pytest.raises(ValueError):
        amfi.fetch_history(date(2025, 1, 1), date(2025, 12, 31))


def test_mfapi_parse_sorts_ascending_and_keeps_bad_values_visible():
    body = json.dumps({"meta": {"scheme_code": 1}, "status": "SUCCESS", "data": [
        {"date": "31-10-2026", "nav": "22.15"}, {"date": "30-10-2026", "nav": "N.A."}, {"date": "bad", "nav": "1"},
        {"date": "29-10-2026", "nav": "22.04"}]}).encode()
    h = mfapi.parse_history("1", body)
    assert [o[0] for o in h.observations] == [date(2026, 10, 29), date(2026, 10, 30), date(2026, 10, 31)]
    assert h.observations[1][1] is None  # kept as missing so the quality check can flag it


def test_truncated_mfapi_json_is_retried_then_fails(monkeypatch):
    calls = {"n": 0}

    class R:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): calls["n"] += 1; return b'{"meta": {"a": 1}, "data": [{"date": "01-0'

    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: R())
    slept = []
    with pytest.raises(FetchError):
        fetch("http://x", retries=2, validate=mfapi._validate_json, sleep=slept.append)
    assert calls["n"] == 3 and slept == [1.5, 3.0]  # exponential backoff


def test_http_404_is_not_retried(monkeypatch):
    import urllib.error

    calls = {"n": 0}

    def boom(*a, **k):
        calls["n"] += 1
        raise urllib.error.HTTPError("http://x", 404, "nf", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", boom)
    with pytest.raises(FetchError):
        fetch("http://x", retries=3, sleep=lambda s: None)
    assert calls["n"] == 1
