"""Generate docs/data_dictionary/yahoo_funds_clean.md and data_quality_report.md from the raw CSV.

Run: .venv/bin/python scripts/generate_data_docs.py
Statistics come from the file; descriptions of derived columns were verified by hand on sample rows
(see 'Verified' notes). Columns marked 'inferred' were not verified against an upstream spec.
"""
import csv
import math
import statistics
from collections import Counter
from pathlib import Path

from data_pipeline.ingestion.yahoo_csv import parse_file, summarize

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "data" / "raw" / "yahoo" / "yahoo_funds_clean.csv"
OUT = ROOT / "docs" / "data_dictionary"

DESC = {
    "Rank": "Row rank in the upstream export (unique 1..N). Not a performance rank.",
    "Symbol": "Yahoo Finance / Morningstar ticker (e.g. 0P00005UMY.BO). External identifier only.",
    "Name": "Yahoo's abbreviated scheme name (plan and option abbreviated in the name).",
    "Change %": "Latest daily price change, percent.",
    "Price (Intraday)": "Latest price/NAV as reported by Yahoo. Snapshot date unknown.",
    "YTD Return": "Year-to-date return, percent. Verified current: matches NAV-derived value at the snapshot date.",
    "3-Mo Return": "3-month return, percent. Verified current at the snapshot date.",
    "1-Year Return": "1-year return, percent. NOT aligned to the snapshot date: per-fund end dates range from early August to late October.",
    "3-Year Return": "3-year return, percent, ANNUALISED (verified against NAV). Measured to dates that differ by fund, often weeks to months before the snapshot: indicative only.",
    "5-Year Return": "5-year return, percent, ANNUALISED (verified against NAV). Not aligned to the snapshot date (see 3-Year Return).",
    "Net Assets": "Fund net assets in rupees. Repeated across share classes of one fund; 32% missing.",
    "50 Day Avg": "50-day average price.",
    "200 Day Avg": "200-day average price.",
    "52 Week Low": "52-week low price.",
    "52 Week High": "52-week high price.",
    "Initial Investment": "Minimum initial investment in rupees.",
    "AMC": "Asset management company (or insurer for ULIP-type funds).",
    "Category": "Yahoo/Morningstar category (49 values).",
    "52 Week Price % Change": "Price change over 52 weeks, percent.",
    "Market Cap Value": "Yahoo field, meaning unclear (often 0 or small). Do not use until understood.",
    "plan_type": "Derived: Direct / Regular / Institutional / Unspecified. Unspecified is kept, never guessed.",
    "option_type": "Derived: Growth / IDCW / Unspecified.",
    "idcw_mode": "Derived: Payout / Reinvestment / Transfer for IDCW options.",
    "idcw_freq": "Derived: Daily / Weekly / Monthly / Quarterly / Annual for IDCW options.",
    "base_fund": "Derived normalised fund name used to group share classes of one fund.",
    "is_insurer_fund": "Derived flag: insurer-linked fund (not an AMFI mutual fund scheme).",
    "is_discontinued": "Derived flag.",
    "n_share_classes": "Derived: number of rows sharing base_fund.",
    "pct_from_52w_high": "Verified: price / 52w high - 1 (fraction).",
    "pct_from_52w_low": "Verified: price / 52w low - 1 (fraction).",
    "range_position": "Verified: (price - low) / (high - low), 0..1.",
    "range_width_pct": "Verified: (high - low) / low (fraction).",
    "trend_50_200": "Verified: 50d avg / 200d avg - 1.",
    "price_vs_50d": "Verified: price / 50d avg - 1.",
    "price_vs_200d": "Derived analogously to price_vs_50d (inferred).",
    "ret_1y_minus_3y": "Verified: 1Y return - 3Y return (percentage points).",
    "ret_3y_minus_5y": "3Y return - 5Y return (percentage points).",
    "ret_ytd_minus_3m": "Verified: YTD return - 3M return (percentage points).",
    "ret_mean_1_3_5": "Verified: mean of 1Y, 3Y, 5Y returns.",
    "ret_std_1_3_5": "Verified: sample standard deviation of 1Y, 3Y, 5Y returns. Dispersion across horizons, NOT volatility.",
    "return_per_range": "Verified: 1Y return / (range_width_pct * 100). Infinite where the 52w range is zero (3 rows; stored as null).",
    "log_net_assets": "Verified: log10(Net Assets).",
    "log_min_invest": "Verified: log10(Initial Investment).",
    "min_invest_missing": "Flag: Initial Investment missing (0/1).",
    "net_assets_missing": "Flag: Net Assets missing (0/1).",
    "asset_tier": "Derived: Equity / Debt / Hybrid / Other.",
    "split": "Upstream train/test label. AUDIT ONLY. Never a feature; not a point-in-time split.",
}


def describe(col: str) -> str:
    if col in DESC:
        return DESC[col]
    if col.endswith("_cat_pct"):
        return "Within-category percentile of the metric (0..1). Derivation inferred, not documented upstream."
    if col.endswith("_cat_z"):
        return "Within-category z-score of the metric. Derivation inferred, not documented upstream."
    return "(undocumented)"


def main() -> None:
    parsed = parse_file(CSV)
    with CSV.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    cols = list(rows[0].keys())
    n = len(rows)

    lines = [
        "# Data dictionary — yahoo_funds_clean.csv",
        "",
        f"Generated by `scripts/generate_data_docs.py`. {n:,} rows, {len(cols)} columns, SHA-256 `{parsed.sha256}`.",
        "Snapshot date unknown. Single cross-section: no history.",
        "",
        "| # | Column | Type | Null % | Min | Median | Max | Description |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for i, c in enumerate(cols, 1):
        vals = [r[c] for r in rows]
        blank = sum(1 for v in vals if v.strip() == "")
        nums = []
        for v in vals:
            try:
                x = float(v)
                if math.isfinite(x):
                    nums.append(x)
            except ValueError:
                pass
        numeric = len(nums) >= 0.9 * (n - blank) and nums
        if numeric:
            typ = "number"
            lo, med, hi = f"{min(nums):.4g}", f"{statistics.median(nums):.4g}", f"{max(nums):.4g}"
        else:
            typ = "text/bool"
            lo = med = hi = ""
        lines.append(f"| {i} | `{c}` | {typ} | {100 * blank / n:.1f} | {lo} | {med} | {hi} | {describe(c)} |")
    (OUT / "yahoo_funds_clean.md").write_text("\n".join(lines) + "\n")

    s = summarize(parsed)
    fam_dg = {}
    for r in parsed.rows:
        fam_dg.setdefault((r.base_fund, r.amc), set()).add((r.plan_type, r.option_type))
    with_dg = sum(1 for v in fam_dg.values() if ("Direct", "Growth") in v)
    tier = Counter(r.asset_tier for r in parsed.rows)
    issues = Counter((i.rule, i.severity) for r in parsed.rows for i in r.issues)
    q = [
        "# Data quality report — yahoo_funds_clean.csv",
        "",
        f"Generated by `scripts/generate_data_docs.py` from `{CSV.name}` (SHA-256 `{parsed.sha256}`).",
        "",
        "## Facts",
        f"- Rows: {s['rows']:,}; columns: {s['columns']}; duplicate symbols: {len(parsed.file_issues)}.",
        f"- AMCs: {len({r.amc for r in parsed.rows})}; categories: {len({r.category for r in parsed.rows})}; "
        f"fund families (base_fund + AMC): {s['families']:,}.",
        f"- Asset tier: {dict(tier)}.",
        f"- Plan unspecified: {s['plan_unspecified']:,}; option unspecified: {s['option_unspecified']:,} (retained, not guessed).",
        f"- Insurer funds: {s['insurer_funds']}; discontinued: {s['discontinued_funds']}.",
        f"- Families with at least one Direct+Growth share class: {with_dg:,} of {s['families']:,} "
        f"({100 * with_dg / s['families']:.0f}%). Relevant to ADR 003 (ranking series).",
        "",
        "## Missing values (kept as null, never imputed)",
        "| Field | Null rows | % |",
        "|---|---|---|",
    ]
    for k, v in s["null_counts"].items():
        if v:
            q.append(f"| {k} | {v:,} | {100 * v / n:.1f} |")
    q += ["", "## Row-level issues raised by validation rules", "| Rule | Severity | Rows |", "|---|---|---|"]
    for (rule, sev), v in sorted(issues.items()):
        q.append(f"| {rule} | {sev} | {v} |")
    q += [
        "",
        f"Quarantined rows (error-severity rules): {s['quarantined']}.",
        "",
        "## Notes",
        "- No row triggered a quarantine rule, so none is quarantined at this time. Rules are in "
        "`data_pipeline/data_pipeline/ingestion/yahoo_csv.py`.",
        "- Net Assets repeats across share classes: aggregate by family before summing.",
        "- Return fields: YTD and 3M match NAV-derived values at the snapshot date; 1Y/3Y/5Y are annualised (3Y/5Y) but measured to earlier, fund-specific dates. The `*_cat_pct`/`*_cat_z` columns for 1Y/3Y/5Y inherit this. See the Data Coverage page.",
    ]
    (OUT / "data_quality_report.md").write_text("\n".join(q) + "\n")
    print("written", OUT)


if __name__ == "__main__":
    main()
