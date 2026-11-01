"""Screener: validated filter tree -> parameterised SQL.

No user text is ever concatenated into SQL. Fields and operators come from a whitelist.
SQL comparison with NULL is never true, so missing values never match a numeric condition.
Percentile-like fields are exposed in percent (0-100), fractions (price_vs_200d etc.) also in percent.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import Float, and_, cast, false, not_, or_, true
from sqlalchemy.sql.elements import ColumnElement

from app.models import AMC, FundCategory, FundScore, FundSnapshot, Scheme, SchemeMetric

MAX_DEPTH = 3
MAX_CONDITIONS = 25


@dataclass(frozen=True)
class FieldDef:
    key: str
    label: str
    kind: Literal["number", "category", "bool"]
    group: str
    unit: str = ""
    feature: str | None = None  # key inside FundSnapshot.features
    column: Any = None  # SQLAlchemy column for non-feature fields
    scale: float = 1.0  # multiply stored value to get displayed unit


def _f(key, label, group, unit, *, feature=None, column=None, scale=1.0, kind="number") -> FieldDef:
    return FieldDef(key, label, kind, group, unit, feature, column, scale)


FIELDS: dict[str, FieldDef] = {
    f.key: f
    for f in [
        _f("price", "Price / NAV", "Price", "₹", column=FundSnapshot.price),
        _f("change_pct", "Day change", "Price", "%", column=FundSnapshot.change_pct),
        _f("ytd_return", "YTD return", "Returns", "%", column=FundSnapshot.ytd_return),
        _f("return_3m", "3M return", "Returns", "%", column=FundSnapshot.return_3m),
        _f("return_1y", "1Y return", "Returns", "%", column=FundSnapshot.return_1y),
        _f("return_3y", "3Y return", "Returns", "%", column=FundSnapshot.return_3y),
        _f("return_5y", "5Y return", "Returns", "%", column=FundSnapshot.return_5y),
        _f("net_assets", "Net assets", "Size", "₹ Cr", column=FundSnapshot.net_assets, scale=1e-7),
        _f("initial_investment", "Min. investment", "Size", "₹", column=FundSnapshot.initial_investment),
        _f("cat_pct_ytd", "YTD category percentile", "Category-relative", "pctile", feature="ytd_return_cat_pct", scale=100),
        _f("cat_pct_3m", "3M category percentile", "Category-relative", "pctile", feature="3mo_return_cat_pct", scale=100),
        _f("cat_pct_1y", "1Y category percentile", "Category-relative", "pctile", feature="1year_return_cat_pct", scale=100),
        _f("cat_pct_3y", "3Y category percentile", "Category-relative", "pctile", feature="3year_return_cat_pct", scale=100),
        _f("cat_pct_5y", "5Y category percentile", "Category-relative", "pctile", feature="5year_return_cat_pct", scale=100),
        _f("cat_pct_range", "52w range position, category percentile", "Category-relative", "pctile", feature="range_position_cat_pct", scale=100),
        _f("cat_pct_trend", "Trend (50d/200d), category percentile", "Category-relative", "pctile", feature="trend_50_200_cat_pct", scale=100),
        _f("cat_pct_size", "Size, category percentile", "Category-relative", "pctile", feature="log_net_assets_cat_pct", scale=100),
        _f("cat_z_1y", "1Y category z-score", "Category-relative", "z", feature="1year_return_cat_z"),
        _f("cat_z_3y", "3Y category z-score", "Category-relative", "z", feature="3year_return_cat_z"),
        _f("cat_z_5y", "5Y category z-score", "Category-relative", "z", feature="5year_return_cat_z"),
        _f("price_vs_50d", "Price vs 50-day avg", "Trend", "%", feature="price_vs_50d", scale=100),
        _f("price_vs_200d", "Price vs 200-day avg", "Trend", "%", feature="price_vs_200d", scale=100),
        _f("trend_50_200", "50d avg vs 200d avg", "Trend", "%", feature="trend_50_200", scale=100),
        _f("range_position", "52w range position (0-100)", "Trend", "%", feature="range_position", scale=100),
        _f("pct_from_52w_high", "Distance from 52w high", "Trend", "%", feature="pct_from_52w_high", scale=100),
        _f("ret_mean_1_3_5", "Mean of 1Y/3Y/5Y returns", "Returns", "%", feature="ret_mean_1_3_5"),
        _f("nav_ret_1y", "1Y return (from NAV)", "NAV-derived", "%", column=SchemeMetric.ret_1y),
        _f("nav_ret_3y", "3Y return, annualised (from NAV)", "NAV-derived", "% p.a.", column=SchemeMetric.ret_3y),
        _f("nav_ret_5y", "5Y return, annualised (from NAV)", "NAV-derived", "% p.a.", column=SchemeMetric.ret_5y),
        _f("vol_3y", "3Y volatility", "NAV-derived", "%", column=SchemeMetric.vol_3y),
        _f("sharpe_3y", "3Y Sharpe ratio", "NAV-derived", "ratio", column=SchemeMetric.sharpe_3y),
        _f("sortino_3y", "3Y Sortino ratio", "NAV-derived", "ratio", column=SchemeMetric.sortino_3y),
        _f("max_dd_3y", "3Y max drawdown", "NAV-derived", "%", column=SchemeMetric.max_dd_3y),
        _f("calmar_3y", "3Y Calmar ratio", "NAV-derived", "ratio", column=SchemeMetric.calmar_3y),
        _f("beta_3y", "3Y beta (vs category average)", "NAV-derived", "ratio", column=SchemeMetric.beta_3y),
        _f("alpha_3y", "3Y alpha (vs category average)", "NAV-derived", "% p.a.", column=SchemeMetric.alpha_3y),
        _f("te_3y", "3Y tracking error (vs category average)", "NAV-derived", "%", column=SchemeMetric.te_3y),
        _f("ir_3y", "3Y information ratio (vs category average)", "NAV-derived", "ratio", column=SchemeMetric.ir_3y),
        _f("peer_pct_ret_3y", "3Y return, peer percentile", "NAV-derived", "pctile", column=SchemeMetric.pctile_ret_3y),
        _f("peer_pct_sharpe_3y", "3Y Sharpe, peer percentile", "NAV-derived", "pctile", column=SchemeMetric.pctile_sharpe_3y),
        _f("peer_pct_max_dd_3y", "3Y drawdown, peer percentile", "NAV-derived", "pctile", column=SchemeMetric.pctile_max_dd_3y),
        _f("peer_pct_vol_3y", "3Y volatility, peer percentile (lower vol = higher)", "NAV-derived", "pctile", column=SchemeMetric.pctile_vol_3y),
        _f("quant_score", "QuantSynthica score (peer-relative)", "Quant score", "0-100", column=FundScore.composite),
        _f("quant_coverage", "Score data completeness", "Quant score", "%", column=FundScore.coverage, scale=100),
        _f("quant_rank", "Rank within peer group", "Quant score", "rank", column=FundScore.rank_in_group),
        *[_f(f"quant_f_{k}", f"{lbl} factor score", "Quant score", "0-100",
             column=cast(FundScore.detail.op("->")("factors").op("->>")(k), Float))
          for k, lbl in (("performance", "Performance"), ("risk_adjusted", "Risk-adjusted"), ("consistency", "Consistency"),
                         ("downside", "Downside protection"), ("momentum", "Momentum"))],
        _f("amc", "AMC", "Fund", "", column=AMC.name, kind="category"),
        _f("category", "Category", "Fund", "", column=FundCategory.name, kind="category"),
        _f("asset_tier", "Asset tier", "Fund", "", column=Scheme.asset_tier, kind="category"),
        _f("plan_type", "Plan", "Fund", "", column=Scheme.plan_type, kind="category"),
        _f("option_type", "Option", "Fund", "", column=Scheme.option_type, kind="category"),
        _f("idcw_freq", "IDCW frequency", "Fund", "", column=Scheme.idcw_freq, kind="category"),
        _f("is_insurer_fund", "Insurer fund", "Flags", "", column=Scheme.is_insurer_fund, kind="bool"),
        _f("is_discontinued", "Discontinued", "Flags", "", column=Scheme.is_discontinued, kind="bool"),
    ]
}

NUMBER_OPS = {"gt", "gte", "lt", "lte", "eq", "neq", "between", "is_null", "not_null"}
CATEGORY_OPS = {"eq", "neq", "in", "not_in", "is_null", "not_null"}
BOOL_OPS = {"eq"}


class Condition(BaseModel):
    field: str
    op: str
    value: float | str | bool | list[float | str] | None = None

    @model_validator(mode="after")
    def check(self) -> Condition:
        fd = FIELDS.get(self.field)
        if fd is None:
            raise ValueError(f"unknown field '{self.field}'")
        allowed = {"number": NUMBER_OPS, "category": CATEGORY_OPS, "bool": BOOL_OPS}[fd.kind]
        if self.op not in allowed:
            raise ValueError(f"operator '{self.op}' not allowed for {fd.kind} field '{self.field}'")
        v = self.value
        if self.op in {"is_null", "not_null"}:
            return self
        if self.op == "between":
            if not (isinstance(v, list) and len(v) == 2 and all(isinstance(x, (int, float)) for x in v)):
                raise ValueError("between needs [low, high]")
        elif self.op in {"in", "not_in"}:
            if not (isinstance(v, list) and 0 < len(v) <= 100 and all(isinstance(x, str) for x in v)):
                raise ValueError("in/not_in need a non-empty list of strings")
        elif fd.kind == "number":
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise ValueError("numeric value required")
        elif fd.kind == "category":
            if not isinstance(v, str):
                raise ValueError("string value required")
        elif fd.kind == "bool":
            if not isinstance(v, bool):
                raise ValueError("boolean value required")
        return self


class Group(BaseModel):
    op: Literal["and", "or"] = "and"
    items: list[Condition | Group] = Field(default_factory=list)


Group.model_rebuild()
Node = Annotated[Condition | Group, Field()]


def _expr(fd: FieldDef) -> ColumnElement:
    if fd.feature is not None:
        base = cast(FundSnapshot.features.op("->>")(fd.feature), Float)
    else:
        base = fd.column
    return base * fd.scale if fd.scale != 1.0 else base


def _cond(c: Condition) -> ColumnElement:
    fd = FIELDS[c.field]
    e = _expr(fd)
    v = c.value
    match c.op:
        case "is_null":
            return e.is_(None)
        case "not_null":
            return e.is_not(None)
        case "gt":
            return e > v
        case "gte":
            return e >= v
        case "lt":
            return e < v
        case "lte":
            return e <= v
        case "eq":
            return e == v
        case "neq":
            # NULL <> x is NULL (not true): missing values never match, consistent with other operators
            return e != v
        case "between":
            lo, hi = sorted(v)
            return and_(e >= lo, e <= hi)
        case "in":
            return e.in_(v)
        case "not_in":
            return and_(e.is_not(None), not_(e.in_(v)))
    raise ValueError(c.op)  # unreachable: validated


def _count(node: Group | Condition) -> int:
    return 1 if isinstance(node, Condition) else sum(_count(i) for i in node.items)


def _depth(node: Group | Condition) -> int:
    return 0 if isinstance(node, Condition) else 1 + max((_depth(i) for i in node.items), default=0)


def validate_tree(root: Group) -> None:
    if _depth(root) > MAX_DEPTH:
        raise ValueError(f"filter nesting deeper than {MAX_DEPTH}")
    if _count(root) > MAX_CONDITIONS:
        raise ValueError(f"more than {MAX_CONDITIONS} conditions")


def build_where(node: Group | Condition) -> ColumnElement:
    if isinstance(node, Condition):
        return _cond(node)
    parts = [build_where(i) for i in node.items]
    if not parts:
        return true() if node.op == "and" else false()
    return and_(*parts) if node.op == "and" else or_(*parts)


def field_catalog() -> list[dict[str, Any]]:
    ops = {"number": sorted(NUMBER_OPS), "category": sorted(CATEGORY_OPS), "bool": sorted(BOOL_OPS)}
    return [
        {"key": f.key, "label": f.label, "kind": f.kind, "group": f.group, "unit": f.unit, "ops": ops[f.kind]}
        for f in FIELDS.values()
    ]


def sort_expr(key: str) -> ColumnElement | None:
    if key == "name":
        return Scheme.name
    fd = FIELDS.get(key)
    if fd is None or fd.kind != "number":
        return None
    return _expr(fd)
