"""Panel helpers: many funds on one business-day calendar.

A panel is a DataFrame of NAVs (rows = dates, columns = fund codes). Missing NAVs are NaN. To compute returns we
carry a NAV forward for at most FFILL_LIMIT business days (a holiday gap), never longer: a fund that stops
publishing becomes NaN instead of showing a long run of zero returns.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from quant_engine.common import suspect_moves

FFILL_LIMIT = 3


def build_panel(navs: dict[str, pd.Series], exclude_suspect: bool = True) -> tuple[pd.DataFrame, list[str]]:
    """Returns (NAV panel on business days, codes dropped because of a suspect NAV discontinuity)."""
    dropped: list[str] = []
    cols = {}
    for code, s in navs.items():
        s = s[~s.index.duplicated(keep="last")].sort_index()
        s = s[(s > 0) & np.isfinite(s)]
        if len(s) < 30:
            continue
        if exclude_suspect and suspect_moves(s):
            dropped.append(code)
            continue
        cols[code] = s
    if not cols:
        return pd.DataFrame(), dropped
    idx = pd.bdate_range(min(s.index[0] for s in cols.values()), max(s.index[-1] for s in cols.values()))
    panel = pd.DataFrame({c: s.reindex(idx.union(s.index)).ffill(limit=FFILL_LIMIT).reindex(idx) for c, s in cols.items()})
    # a NAV carried forward past its last real observation must not extend a fund's life
    for c, s in cols.items():
        panel.loc[panel.index > s.index[-1] + pd.Timedelta(days=FFILL_LIMIT + 4), c] = np.nan
    return panel, dropped


def daily_returns(panel: pd.DataFrame) -> pd.DataFrame:
    return panel.pct_change(fill_method=None)


def monthly_return_panel(rets: pd.DataFrame) -> pd.DataFrame:
    """Compounded calendar-month returns per fund. A month with no valid daily return is NaN."""
    g = rets.groupby([rets.index.year, rets.index.month])
    out = g.apply(lambda x: (1 + x.fillna(0)).prod() - 1).where(g.count() > 0)
    out.index = pd.PeriodIndex([pd.Period(year=y, month=m, freq="M") for y, m in out.index], freq="M")
    return out


def last_on_or_before(index: pd.DatetimeIndex, ts: pd.Timestamp) -> pd.Timestamp | None:
    pos = index.searchsorted(ts, side="right") - 1
    return index[pos] if pos >= 0 else None


def month_ends(index: pd.DatetimeIndex, start: pd.Timestamp, end: pd.Timestamp, step: int = 1) -> list[pd.Timestamp]:
    """Last available business date of each month in [start, end], every `step` months."""
    s = pd.Series(index, index=index)
    last = s.groupby([s.index.year, s.index.month]).last()
    dates = [d for d in last.values if start <= d <= end]
    return list(pd.DatetimeIndex(dates)[::step])
