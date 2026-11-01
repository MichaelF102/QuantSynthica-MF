"""Parse and validate the Yahoo fund snapshot CSV.

Pure Python: no pandas, no database. Missing values stay ``None``; nothing is
imputed or dropped here. Validation emits issues; the caller decides what to do.
"""
from __future__ import annotations

import csv
import hashlib
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# CSV column -> typed field on the snapshot (float unless noted)
NUMERIC_COLUMNS: dict[str, str] = {
    "Price (Intraday)": "price",
    "Change %": "change_pct",
    "YTD Return": "ytd_return",
    "3-Mo Return": "return_3m",
    "1-Year Return": "return_1y",
    "3-Year Return": "return_3y",
    "5-Year Return": "return_5y",
    "Net Assets": "net_assets",
    "50 Day Avg": "avg_50d",
    "200 Day Avg": "avg_200d",
    "52 Week Low": "low_52w",
    "52 Week High": "high_52w",
    "Initial Investment": "initial_investment",
    "Market Cap Value": "market_cap_value",
    "52 Week Price % Change": "price_change_52w_pct",
}

IDENTITY_COLUMNS = {
    "Rank", "Symbol", "Name", "AMC", "Category", "plan_type", "option_type",
    "idcw_mode", "idcw_freq", "base_fund", "is_insurer_fund", "is_discontinued",
    "n_share_classes", "asset_tier", "split",
}

# Columns that are not stored as features: raw numerics handled above, identity above.
EXCLUDED_FROM_FEATURES = set(NUMERIC_COLUMNS) | IDENTITY_COLUMNS

PLAN_VALUES = {"Direct", "Regular", "Institutional", "Unspecified"}
OPTION_VALUES = {"Growth", "IDCW", "Unspecified"}
BOOL_TRUE = {"true", "1", "yes"}


@dataclass(frozen=True)
class Issue:
    rule: str
    severity: str  # "error" (quarantine/reject), "warning"
    symbol: str | None
    detail: dict[str, Any]


@dataclass
class FundRow:
    symbol: str
    name: str
    amc: str
    category: str
    asset_tier: str
    plan_type: str
    option_type: str
    idcw_mode: str | None
    idcw_freq: str | None
    base_fund: str
    is_insurer_fund: bool
    is_discontinued: bool
    n_share_classes: int | None
    source_rank: int | None
    values: dict[str, float | None]
    features: dict[str, float | None]
    audit: dict[str, Any]
    issues: list[Issue] = field(default_factory=list)

    @property
    def quarantined(self) -> bool:
        return any(i.severity == "error" for i in self.issues)


@dataclass
class ParsedFile:
    path: str
    sha256: str
    columns: list[str]
    rows: list[FundRow]
    file_issues: list[Issue]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _num(raw: str | None) -> float | None:
    if raw is None:
        return None
    raw = raw.strip()
    if raw == "":
        return None
    try:
        val = float(raw)
    except ValueError:
        return None
    # inf/nan are not valid JSON and not meaningful values; treat as missing.
    return val if math.isfinite(val) else None


def _is_nonfinite(raw: str | None) -> bool:
    return (raw or "").strip().lower() in {"inf", "-inf", "+inf", "infinity", "-infinity", "nan"}


def _bool(raw: str | None) -> bool:
    return (raw or "").strip().lower() in BOOL_TRUE


def _text(raw: str | None) -> str | None:
    raw = (raw or "").strip()
    return raw or None


def parse_file(path: Path) -> ParsedFile:
    sha = sha256_file(path)
    rows: list[FundRow] = []
    file_issues: list[Issue] = []
    seen: dict[str, int] = {}
    # utf-8-sig strips the BOM that precedes the "Rank" header.
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        columns = list(reader.fieldnames or [])
        required = {"Symbol", "Name", "AMC", "Category", "Price (Intraday)", "base_fund"}
        missing = required - set(columns)
        if missing:
            raise ValueError(f"CSV missing required columns: {sorted(missing)}")
        for line_no, rec in enumerate(reader, start=2):
            symbol = (rec.get("Symbol") or "").strip()
            if not symbol:
                file_issues.append(Issue("R000_missing_symbol", "error", None, {"line": line_no}))
                continue
            if symbol in seen:
                file_issues.append(
                    Issue("R010_duplicate_symbol", "error", symbol, {"line": line_no, "first_line": seen[symbol]})
                )
                continue
            seen[symbol] = line_no

            values: dict[str, float | None] = {f: _num(rec.get(c)) for c, f in NUMERIC_COLUMNS.items()}
            features = {
                c: _num(v)
                for c, v in rec.items()
                if c not in EXCLUDED_FROM_FEATURES and c is not None
            }
            row = FundRow(
                symbol=symbol,
                name=(rec.get("Name") or "").strip(),
                amc=(rec.get("AMC") or "").strip(),
                category=(rec.get("Category") or "").strip(),
                asset_tier=(rec.get("asset_tier") or "").strip() or "Unspecified",
                plan_type=(rec.get("plan_type") or "").strip() or "Unspecified",
                option_type=(rec.get("option_type") or "").strip() or "Unspecified",
                idcw_mode=_text(rec.get("idcw_mode")),
                idcw_freq=_text(rec.get("idcw_freq")),
                base_fund=(rec.get("base_fund") or "").strip(),
                is_insurer_fund=_bool(rec.get("is_insurer_fund")),
                is_discontinued=_bool(rec.get("is_discontinued")),
                n_share_classes=int(v) if (v := _num(rec.get("n_share_classes"))) is not None else None,
                source_rank=int(v) if (v := _num(rec.get("Rank"))) is not None else None,
                values=values,
                features=features,
                # `split` is a train/test label from upstream modelling. Kept for audit only.
                audit={"split": _text(rec.get("split")), "csv_line": line_no},
            )
            nonfinite = sorted(c for c, v in rec.items() if c and _is_nonfinite(v))
            if nonfinite:
                row.issues.append(Issue("R040_nonfinite_value", "warning", symbol, {"columns": nonfinite}))
            row.issues.extend(validate_row(row))
            rows.append(row)
    return ParsedFile(str(path), sha, columns, rows, file_issues)


def validate_row(row: FundRow) -> list[Issue]:
    """Row-level checks. Errors quarantine the row (kept, flagged); warnings only flag."""
    v = row.values
    out: list[Issue] = []
    sym = row.symbol

    if not row.name:
        out.append(Issue("R001_missing_name", "error", sym, {}))
    if not row.amc:
        out.append(Issue("R002_missing_amc", "error", sym, {}))
    if not row.base_fund:
        out.append(Issue("R003_missing_base_fund", "warning", sym, {}))

    price, lo, hi = v["price"], v["low_52w"], v["high_52w"]
    if price is None or price <= 0:
        out.append(Issue("R020_nonpositive_price", "error", sym, {"price": price}))
    if lo is not None and hi is not None and lo > hi:
        out.append(Issue("R021_low_above_high", "error", sym, {"low": lo, "high": hi}))
    if price and hi and price > hi * 1.02:
        out.append(Issue("R022_price_above_52w_high", "warning", sym, {"price": price, "high": hi}))
    if price and lo and price < lo * 0.98:
        out.append(Issue("R023_price_below_52w_low", "warning", sym, {"price": price, "low": lo}))
    if lo and hi and lo > 0 and hi / lo > 5:
        out.append(Issue("R024_extreme_52w_range", "warning", sym, {"low": lo, "high": hi}))
    for key, rule in (("avg_50d", "R025_price_vs_50d_extreme"), ("avg_200d", "R026_price_vs_200d_extreme")):
        avg = v[key]
        if price and avg and avg > 0 and not (1 / 3 <= price / avg <= 3):
            out.append(Issue(rule, "warning", sym, {"price": price, "avg": avg}))
    ch = v["change_pct"]
    if ch is not None and abs(ch) > 25:
        out.append(Issue("R027_large_daily_change", "warning", sym, {"change_pct": ch}))
    for key in ("return_1y", "return_3y", "return_5y"):
        r = v[key]
        if r is not None and abs(r) > 150:
            out.append(Issue("R028_extreme_return", "warning", sym, {"field": key, "value": r}))
    if row.plan_type not in PLAN_VALUES:
        out.append(Issue("R030_unknown_plan_type", "warning", sym, {"value": row.plan_type}))
    if row.option_type not in OPTION_VALUES:
        out.append(Issue("R031_unknown_option_type", "warning", sym, {"value": row.option_type}))
    return out


def summarize(parsed: ParsedFile) -> dict[str, Any]:
    """Counts used by the data-quality report (info-level facts, not per-row issues)."""
    rows = parsed.rows
    n = len(rows)

    def count(pred) -> int:
        return sum(1 for r in rows if pred(r))

    null_counts = {
        f: count(lambda r, f=f: r.values[f] is None) for f in NUMERIC_COLUMNS.values()
    }
    return {
        "rows": n,
        "columns": len(parsed.columns),
        "plan_unspecified": count(lambda r: r.plan_type == "Unspecified"),
        "option_unspecified": count(lambda r: r.option_type == "Unspecified"),
        "insurer_funds": count(lambda r: r.is_insurer_fund),
        "discontinued_funds": count(lambda r: r.is_discontinued),
        "families": len({(r.base_fund, r.amc) for r in rows}),
        "null_counts": null_counts,
        "quarantined": count(lambda r: r.quarantined),
    }
