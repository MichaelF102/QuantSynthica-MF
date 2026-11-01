"""Risk analytics from period returns / NAV. Pure functions; see common.py for conventions.

Sign conventions: VaR / CVaR are returns (negative numbers = loss), in percent. Drawdowns are negative percents.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from statistics import NormalDist

from quant_engine.common import (
    MIN_OBS,
    MIN_RATIO_VOL,
    TRADING_DAYS,
    Metric,
    align,
    clean_nav,
    coverage,
    period_rf,
)



def _skew(x: np.ndarray) -> float:
    """Sample skewness with the small-sample correction (G1); equals scipy.stats.skew(bias=False). Written out so that the
    API process does not import scipy.stats (~60 MB) just for this."""
    n = len(x)
    m = x - x.mean()
    m2, m3 = (m ** 2).mean(), (m ** 3).mean()
    return float(m3 / m2 ** 1.5 * math.sqrt(n * (n - 1)) / (n - 2)) if m2 > 0 and n > 2 else float("nan")


def _excess_kurtosis(x: np.ndarray) -> float:
    """Sample excess kurtosis with the small-sample correction (G2); equals scipy.stats.kurtosis(bias=False)."""
    n = len(x)
    m = x - x.mean()
    m2, m4 = (m ** 2).mean(), (m ** 4).mean()
    if m2 <= 0 or n <= 3:
        return float("nan")
    g2 = m4 / m2 ** 2 - 3.0
    return float(((n + 1) * g2 + 6.0) * (n - 1) / ((n - 2) * (n - 3)))

def _span(r: pd.Series) -> dict:
    if r.empty:
        return {}
    return {"window_start": r.index[0].date(), "window_end": r.index[-1].date(), "n_obs": len(r),
            "coverage": coverage(len(r), r.index[0], r.index[-1])}


def _short(name: str, unit: str, r: pd.Series, minimum: int = MIN_OBS) -> Metric | None:
    if len(r) < minimum:
        return Metric(name, None, unit, n_obs=len(r), note=f"fewer than {minimum} observations")
    return None


def annualised_volatility(r: pd.Series) -> Metric:
    short = _short("volatility", "%", r)
    if short:
        return short
    return Metric("volatility", float(r.std(ddof=1) * math.sqrt(TRADING_DAYS) * 100), "%", **_span(r))


def rolling_volatility(r: pd.Series, window: int = TRADING_DAYS) -> pd.Series:
    return (r.rolling(window, min_periods=window).std(ddof=1) * math.sqrt(TRADING_DAYS) * 100).dropna()


def downside_deviation(r: pd.Series, mar: float | pd.Series = 0.0) -> Metric:
    """Annualised root-mean-square of shortfalls below the minimum acceptable return (per period); all periods in the denominator."""
    short = _short("downside_deviation", "%", r)
    if short:
        return short
    m = mar if isinstance(mar, pd.Series) else pd.Series(float(mar), index=r.index)
    shortfall = np.minimum(r - m.reindex(r.index), 0.0)
    return Metric("downside_deviation", float(math.sqrt((shortfall**2).mean()) * math.sqrt(TRADING_DAYS) * 100), "%", **_span(r))


def sharpe_ratio(r: pd.Series, rf: pd.Series | float | None = None) -> Metric:
    short = _short("sharpe_ratio", "ratio", r)
    if short:
        return short
    rfp = period_rf(rf, r.index)
    ex = (r - rfp).dropna()
    if len(ex) < MIN_OBS:
        return Metric("sharpe_ratio", None, "ratio", n_obs=len(ex), note="too few observations with a risk-free rate")
    sd = ex.std(ddof=1)
    if not sd or sd < 1e-12:
        return Metric("sharpe_ratio", None, "ratio", **_span(ex), note="zero volatility")
    if sd * math.sqrt(TRADING_DAYS) * 100 < MIN_RATIO_VOL:
        return Metric("sharpe_ratio", None, "ratio", **_span(ex), note=f"volatility under {MIN_RATIO_VOL}% p.a.: ratio not meaningful")
    return Metric("sharpe_ratio", float(ex.mean() * TRADING_DAYS / (sd * math.sqrt(TRADING_DAYS))), "ratio", **_span(ex))


def sortino_ratio(r: pd.Series, rf: pd.Series | float | None = None) -> Metric:
    short = _short("sortino_ratio", "ratio", r)
    if short:
        return short
    ex = (r - period_rf(rf, r.index)).dropna()
    dd = math.sqrt((np.minimum(ex, 0.0) ** 2).mean()) * math.sqrt(TRADING_DAYS)
    if dd < 1e-12:
        return Metric("sortino_ratio", None, "ratio", **_span(ex), note="no downside periods")
    if ex.std(ddof=1) * math.sqrt(TRADING_DAYS) * 100 < MIN_RATIO_VOL:
        return Metric("sortino_ratio", None, "ratio", **_span(ex), note=f"volatility under {MIN_RATIO_VOL}% p.a.: ratio not meaningful")
    return Metric("sortino_ratio", float(ex.mean() * TRADING_DAYS / dd), "ratio", **_span(ex))


# ---------------------------------------------------------------- drawdowns
def drawdown_series(nav: pd.Series) -> pd.Series:
    nav = clean_nav(nav)
    return (nav / nav.cummax() - 1) * 100


def max_drawdown(nav: pd.Series) -> dict:
    """Largest peak-to-trough fall with its dates, duration and recovery. `recovery_date` is None if not yet recovered."""
    nav = clean_nav(nav)
    if len(nav) < MIN_OBS:
        return {"metric": Metric("max_drawdown", None, "%", n_obs=len(nav), note=f"fewer than {MIN_OBS} observations")}
    dd = drawdown_series(nav)
    trough = dd.idxmin()
    peak = nav.loc[:trough].idxmax()
    after = nav.loc[trough:]
    rec = after[after >= nav.loc[peak]]
    recovery = rec.index[0] if len(rec) else None
    cur = float(dd.iloc[-1])
    return {
        "metric": Metric("max_drawdown", float(dd.min()), "%", nav.index[0].date(), nav.index[-1].date(), len(nav), coverage(len(nav), nav.index[0], nav.index[-1])),
        "peak_date": peak.date(), "trough_date": trough.date(), "recovery_date": recovery.date() if recovery is not None else None,
        "drawdown_days": (trough - peak).days, "recovery_days": (recovery - trough).days if recovery is not None else None,
        "current_drawdown": cur,
    }


def calmar_ratio(nav: pd.Series) -> Metric:
    """CAGR divided by the absolute maximum drawdown over the supplied window."""
    from quant_engine.performance import cagr

    nav = clean_nav(nav)
    c, d = cagr(nav), max_drawdown(nav)["metric"]
    if c.value is None or d.value is None:
        return Metric("calmar_ratio", None, "ratio", n_obs=len(nav), note="CAGR or drawdown unavailable")
    if d.value > -1e-9:
        return Metric("calmar_ratio", None, "ratio", c.window_start, c.window_end, len(nav), note="no drawdown in window")
    return Metric("calmar_ratio", c.value / abs(d.value), "ratio", c.window_start, c.window_end, len(nav), c.coverage)


# ---------------------------------------------------------------- market risk
def beta_alpha(r: pd.Series, b: pd.Series, rf: pd.Series | float | None = None, min_obs: int = 60) -> dict[str, Metric]:
    """OLS of fund excess returns on benchmark excess returns. Alpha is annualised (Jensen), in percent."""
    r, b = align(r, b)
    rfp = period_rf(rf, r.index)
    mask = rfp.notna()
    x, y = (b - rfp)[mask].to_numpy(), (r - rfp)[mask].to_numpy()
    if len(x) < min_obs:
        note = f"fewer than {min_obs} overlapping observations"
        return {k: Metric(k, None, u, n_obs=len(x), note=note) for k, u in (("beta", "ratio"), ("alpha", "%"), ("r_squared", "ratio"))}
    var = x.var(ddof=1)
    if var < 1e-14 or math.sqrt(var) * math.sqrt(TRADING_DAYS) * 100 < MIN_RATIO_VOL:
        note = f"benchmark volatility under {MIN_RATIO_VOL}% p.a.: beta not meaningful"
        return {k: Metric(k, None, u, n_obs=len(x), note=note) for k, u in (("beta", "ratio"), ("alpha", "%"), ("r_squared", "ratio"))}
    beta = float(np.cov(x, y, ddof=1)[0, 1] / var)
    intercept = float(y.mean() - beta * x.mean())
    resid = y - (intercept + beta * x)
    ss_tot = ((y - y.mean()) ** 2).sum()
    r2 = float(1 - (resid**2).sum() / ss_tot) if ss_tot > 0 else None
    span = _span(r[mask])
    return {
        "beta": Metric("beta", beta, "ratio", **span),
        "alpha": Metric("alpha", intercept * TRADING_DAYS * 100, "%", **span),
        "r_squared": Metric("r_squared", r2, "ratio", **span),
    }


def correlation(r: pd.Series, b: pd.Series) -> Metric:
    r, b = align(r, b)
    if len(r) < MIN_OBS:
        return Metric("correlation", None, "ratio", n_obs=len(r), note=f"fewer than {MIN_OBS} overlapping observations")
    return Metric("correlation", float(r.corr(b)), "ratio", **_span(r))


# ---------------------------------------------------------------- tail risk
def var_historical(r: pd.Series, level: float = 0.95) -> Metric:
    name = f"var_{int(level * 100)}"
    short = _short(name, "%", r, 100)
    if short:
        return short
    return Metric(name, float(np.percentile(r, (1 - level) * 100) * 100), "%", **_span(r), note="historical, 1-period")


def cvar_historical(r: pd.Series, level: float = 0.95) -> Metric:
    name = f"cvar_{int(level * 100)}"
    short = _short(name, "%", r, 100)
    if short:
        return short
    cut = np.percentile(r, (1 - level) * 100)
    return Metric(name, float(r[r <= cut].mean() * 100), "%", **_span(r), note="expected shortfall, historical, 1-period")


def var_parametric(r: pd.Series, level: float = 0.95) -> Metric:
    name = f"var_param_{int(level * 100)}"
    short = _short(name, "%", r, 100)
    if short:
        return short
    z = NormalDist().inv_cdf(1 - level)
    return Metric(name, float((r.mean() + z * r.std(ddof=1)) * 100), "%", **_span(r), note="normal, 1-period")


def skewness(r: pd.Series) -> Metric:
    short = _short("skewness", "ratio", r, 100)
    return short or Metric("skewness", _skew(np.asarray(r, dtype=float)), "ratio", **_span(r))


def excess_kurtosis(r: pd.Series) -> Metric:
    short = _short("excess_kurtosis", "ratio", r, 100)
    return short or Metric("excess_kurtosis", _excess_kurtosis(np.asarray(r, dtype=float)), "ratio", **_span(r))
