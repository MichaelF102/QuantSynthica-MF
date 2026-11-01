import csv
from pathlib import Path

import pytest
from data_pipeline.ingestion.yahoo_csv import parse_file, summarize

REAL = Path(__file__).resolve().parents[2] / "data" / "raw" / "yahoo" / "yahoo_funds_clean.csv"

HEADER = [
    "Rank", "Symbol", "Name", "Change %", "Price (Intraday)", "YTD Return", "3-Mo Return", "1-Year Return",
    "3-Year Return", "5-Year Return", "Net Assets", "50 Day Avg", "200 Day Avg", "52 Week Low", "52 Week High",
    "Initial Investment", "AMC", "Category", "52 Week Price % Change", "Market Cap Value", "plan_type",
    "option_type", "idcw_mode", "idcw_freq", "base_fund", "is_insurer_fund", "is_discontinued",
    "n_share_classes", "return_per_range", "asset_tier", "split",
]


def make_row(**over):
    base = {
        "Rank": "1", "Symbol": "S1", "Name": "Fund One", "Change %": "0.1", "Price (Intraday)": "100",
        "YTD Return": "5", "3-Mo Return": "1", "1-Year Return": "10", "3-Year Return": "11", "5-Year Return": "12",
        "Net Assets": "", "50 Day Avg": "99", "200 Day Avg": "98", "52 Week Low": "90", "52 Week High": "110",
        "Initial Investment": "5000", "AMC": "Test AMC", "Category": "Large-Cap", "52 Week Price % Change": "3",
        "Market Cap Value": "", "plan_type": "Unspecified", "option_type": "Unspecified", "idcw_mode": "",
        "idcw_freq": "", "base_fund": "fund one", "is_insurer_fund": "False", "is_discontinued": "False",
        "n_share_classes": "2", "return_per_range": "1.5", "asset_tier": "Equity", "split": "train",
    }
    base.update(over)
    return base


def write(tmp_path, rows, bom=True):
    p = tmp_path / "f.csv"
    with p.open("w", encoding="utf-8-sig" if bom else "utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=HEADER)
        w.writeheader()
        w.writerows(rows)
    return p


def test_bom_handled_and_nulls_preserved(tmp_path):
    parsed = parse_file(write(tmp_path, [make_row()]))
    assert parsed.columns[0] == "Rank"
    r = parsed.rows[0]
    assert r.values["net_assets"] is None  # never imputed
    assert r.plan_type == "Unspecified" and r.option_type == "Unspecified"


def test_split_is_audit_only_not_a_feature(tmp_path):
    r = parse_file(write(tmp_path, [make_row()])).rows[0]
    assert "split" not in r.features
    assert r.audit["split"] == "train"


def test_duplicate_symbol_is_reported_not_silently_dropped(tmp_path):
    parsed = parse_file(write(tmp_path, [make_row(), make_row(Name="Other")]))
    assert len(parsed.rows) == 1
    assert [i.rule for i in parsed.file_issues] == ["R010_duplicate_symbol"]


def test_infinite_values_become_null_with_issue(tmp_path):
    r = parse_file(write(tmp_path, [make_row(return_per_range="Infinity")])).rows[0]
    assert r.features["return_per_range"] is None
    assert any(i.rule == "R040_nonfinite_value" for i in r.issues)


@pytest.mark.parametrize(
    "over,rule,quarantined",
    [
        ({"Price (Intraday)": "0"}, "R020_nonpositive_price", True),
        ({"52 Week Low": "120", "52 Week High": "110"}, "R021_low_above_high", True),
        ({"Price (Intraday)": "200"}, "R022_price_above_52w_high", False),
        ({"52 Week Low": "10", "52 Week High": "100", "Price (Intraday)": "50"}, "R024_extreme_52w_range", False),
        ({"1-Year Return": "400"}, "R028_extreme_return", False),
    ],
)
def test_validation_rules(tmp_path, over, rule, quarantined):
    r = parse_file(write(tmp_path, [make_row(**over)])).rows[0]
    assert rule in {i.rule for i in r.issues}
    assert r.quarantined is quarantined


@pytest.mark.skipif(not REAL.exists(), reason="raw CSV not present")
def test_real_file_facts():
    parsed = parse_file(REAL)
    s = summarize(parsed)
    assert s["rows"] == 3351 and s["columns"] == 63
    assert len({r.symbol for r in parsed.rows}) == 3351
    assert s["plan_unspecified"] == 975 and s["option_unspecified"] == 415
    assert s["null_counts"]["net_assets"] == 1067
    assert not parsed.file_issues
    assert parsed.sha256 == "bab0dbed7eb7981afe0ffe3537c4c47ac89220128c722db983d47e7050311271"
