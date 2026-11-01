"""Synthetic fund universes for tests."""
import numpy as np
import pandas as pd
from quant_engine.panel import daily_returns


def make_panel(n_funds=20, years=8, seed=0, drift=None, vol=0.008, start="2016-01-01", groups=2):
    idx = pd.bdate_range(start, periods=int(years * 252))
    rng = np.random.default_rng(seed)
    market = rng.normal(0.0003, 0.007, len(idx))
    cols = {}
    drift = drift if drift is not None else rng.normal(0.0, 0.00015, n_funds)
    for i in range(n_funds):
        r = drift[i] + 0.8 * market + rng.normal(0, vol, len(idx))
        cols[f"F{i:02d}"] = 100 * np.cumprod(1 + r)
    panel = pd.DataFrame(cols, index=idx)
    g = pd.Series({c: f"G{i % groups}" for i, c in enumerate(panel.columns)})
    return panel, daily_returns(panel), g


def rf_series(index, annual=0.06):
    return pd.Series((1 + annual) ** (1 / 252) - 1, index=index)
