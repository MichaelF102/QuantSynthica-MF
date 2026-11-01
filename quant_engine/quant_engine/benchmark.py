"""Internal reference series built from fund NAVs (no licensed index data).

- category_index: equal-weighted average of peer funds' period returns, compounded to an index (base 100).
  Peers are today's surviving funds, so the index carries survivorship bias; label it as such wherever shown.
- risk_free_proxy: cross-sectional MEDIAN period return of overnight/liquid funds. Not an official rate.
"""
from __future__ import annotations

import pandas as pd

from quant_engine.common import returns, suspect_moves


def _return_panel(navs: dict[str, pd.Series]) -> pd.DataFrame:
    """Return panel that leaves out any fund with a suspect NAV discontinuity (probable split or data error)."""
    ok = {k: v for k, v in navs.items() if not suspect_moves(v)}
    return pd.DataFrame({k: returns(v) for k, v in ok.items()}).sort_index()


def category_index(navs: dict[str, pd.Series], min_funds: int = 5, exclude: str | None = None) -> tuple[pd.Series, int]:
    """Returns (index series, number of funds used). `exclude` removes the fund being analysed (no self-comparison)."""
    use = {k: v for k, v in navs.items() if k != exclude and not suspect_moves(v)}
    if len(use) < min_funds:
        return pd.Series(dtype=float), len(use)
    panel = _return_panel(use)
    count = panel.notna().sum(axis=1)
    avg = panel.mean(axis=1)[count >= min_funds]
    if avg.empty:
        return pd.Series(dtype=float), len(use)
    index = (1 + avg).cumprod() * 100
    index.name = "category_average"
    # prepend the base so the first return is usable
    base_date = avg.index[0] - pd.Timedelta(days=1)
    return pd.concat([pd.Series([100.0], index=[base_date]), index]), len(use)


def category_aggregate(navs: dict[str, pd.Series]) -> tuple[pd.Series, pd.Series, list[str]]:
    """Per-date SUM and COUNT of member returns (suspect-NAV funds left out) plus the member list.

    Saved once per category, this lets `category_index_from_aggregate` build a leave-one-out benchmark for any member
    without loading the other members' NAV histories: mean excluding own = (sum - own) / (count - 1).
    """
    panel = _return_panel(navs)
    if panel.empty:
        return pd.Series(dtype=float), pd.Series(dtype=float), []
    return panel.sum(axis=1), panel.notna().sum(axis=1), list(panel.columns)


def category_index_from_aggregate(total: pd.Series, count: pd.Series, members: list[str], min_funds: int = 5,
                                  own_code: str | None = None, own_nav: pd.Series | None = None) -> tuple[pd.Series, int]:
    """Same result as `category_index` over the same members with `own_code` excluded (up to floating-point rounding)."""
    total, count = total.copy(), count.copy()
    n = len(members)
    if own_code is not None and own_code in members:
        if own_nav is None:
            raise ValueError("own_nav is required to exclude a member")
        own = _return_panel({own_code: own_nav})
        if own_code in own.columns:  # a suspect own series was never in the aggregate
            r = own[own_code].reindex(total.index)
            total = total - r.fillna(0.0)
            count = count - r.notna().astype(int)
            n -= 1
    if n < min_funds:
        return pd.Series(dtype=float), n
    avg = (total / count.where(count > 0))[count >= min_funds].dropna()
    if avg.empty:
        return pd.Series(dtype=float), n
    index = (1 + avg).cumprod() * 100
    index.name = "category_average"
    base_date = avg.index[0] - pd.Timedelta(days=1)
    return pd.concat([pd.Series([100.0], index=[base_date]), index]), n


def risk_free_proxy(navs: dict[str, pd.Series], min_funds: int = 3) -> tuple[pd.Series, int]:
    """Median period return across funds (robust to a single fund's NAV error). Index = dates with >= min_funds funds."""
    navs = {k: v for k, v in navs.items() if not suspect_moves(v)}
    if len(navs) < min_funds:
        return pd.Series(dtype=float), len(navs)
    panel = _return_panel(navs)
    count = panel.notna().sum(axis=1)
    return panel.median(axis=1)[count >= min_funds].rename("rf_proxy"), len(navs)
