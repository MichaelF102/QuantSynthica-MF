"""Low-memory inputs for the portfolio tools.

`quant.bundle` loads every fund's NAV (about 1 GB). A portfolio only needs the funds the user picked (at most 40), a small
risk-free series and a small market-proxy series, so those are loaded on demand; the two small series are precomputed files.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from quant_engine.panel import build_panel
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services import analytics, quant

log = logging.getLogger(__name__)


def _gold() -> Path:
    return Path(get_settings().data_dir) / "gold" / "quant"


def eligible_file() -> Path:
    return _gold() / "eligible_codes.json"


def market_file() -> Path:
    return _gold() / "market_proxy.parquet"


def universe(session: Session) -> pd.DataFrame:
    """Growth, confirmed-link, non-insurer schemes, minus funds whose NAV history was found to be corrupt in the last build."""
    uni = quant.universe(session)
    f = eligible_file()
    if f.exists():
        keep = set(json.loads(f.read_text())["codes"])
        uni = uni.loc[uni.index.intersection(keep)]
    return uni


@dataclass
class Lite:
    uni: pd.DataFrame      # the selected funds only (index = code)
    panel: pd.DataFrame    # NAV of the selected funds on business days
    rf: pd.Series
    dropped: list[str]


def load(session: Session, codes: list[str], uni: pd.DataFrame) -> Lite:
    navs = analytics.load_series(codes)
    panel, dropped = build_panel(navs)
    return Lite(uni.loc[[c for c in codes if c in uni.index]], panel, analytics.risk_free(session), dropped)


def market_proxy(session: Session) -> pd.Series:
    """Equal-weighted Direct equity index. Precomputed by the quant build; computed from the full panel only if the file is absent."""
    f = market_file()
    if f.exists():
        s = pd.read_parquet(f)["market_proxy"]
        s.index = pd.DatetimeIndex(s.index)
        return s
    from quant_engine import regime

    b = quant.bundle(session)
    eq = b.uni[(b.uni["tier"] == "Equity") & (b.uni["plan"] == "Direct")].index
    return regime.market_index(b.rets, list(eq))


def write_light_artifacts(b: "quant.Bundle") -> None:
    """Called after a full build so that a small server never needs the full panel for portfolio features."""
    from quant_engine import regime

    d = _gold()
    d.mkdir(parents=True, exist_ok=True)
    eq = b.uni[(b.uni["tier"] == "Equity") & (b.uni["plan"] == "Direct")].index
    regime.market_index(b.rets, list(eq)).rename("market_proxy").to_frame().to_parquet(market_file())
    eligible_file().write_text(json.dumps({"codes": sorted(b.uni.index), "dropped_suspect_nav": sorted(b.dropped)}))
