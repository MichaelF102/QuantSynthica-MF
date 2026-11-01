"""Market regimes from an internal market proxy (equal-weight average of equity funds; survivors only).

Point-in-time rules
- vol_regime / trend_regime: each date uses only data up to that date (expanding quantiles, trailing windows).
- hmm_regimes: parameters are fitted on the TRAINING window only; later dates use FILTERED probabilities (forward
  algorithm), never smoothed ones, so no future observation influences a past label.
- gmm_regimes: fitted on the whole sample. DESCRIPTIVE ONLY (hindsight); it must not drive point-in-time decisions.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252
MIN_HISTORY_DAYS = 504


def _norm_pdf(x: float, loc: np.ndarray, scale: np.ndarray) -> np.ndarray:
    z = (x - loc) / scale
    return np.exp(-0.5 * z * z) / (scale * np.sqrt(2 * np.pi))


def market_index(rets: pd.DataFrame, codes: list[str], min_funds: int = 5) -> pd.Series:
    sub = rets[[c for c in codes if c in rets.columns]]
    n = sub.notna().sum(axis=1)
    avg = sub.mean(axis=1)[n >= min_funds].dropna()
    idx = (1 + avg).cumprod() * 100
    idx.name = "market_proxy"
    return idx


def vol_regime(index: pd.Series, window: int = 63) -> pd.Series:
    """low / medium / high by the 33rd and 67th percentile of rolling volatility using only past data."""
    r = index.pct_change()
    vol = r.rolling(window).std() * np.sqrt(TRADING_DAYS) * 100
    out = pd.Series(index=index.index, dtype=object)
    vals = vol.to_numpy()
    for i in range(len(vals)):
        if np.isnan(vals[i]) or i < MIN_HISTORY_DAYS:
            continue
        past = vals[: i + 1]
        past = past[~np.isnan(past)]
        lo, hi = np.percentile(past, [33.3, 66.7])
        out.iloc[i] = "low" if vals[i] <= lo else "high" if vals[i] >= hi else "medium"
    return out


def trend_regime(index: pd.Series, ma: int = 200, mom: int = 126) -> pd.Series:
    """bull: above the moving average with positive momentum; bear: below with negative; otherwise sideways."""
    above = index > index.rolling(ma).mean()
    m = index / index.shift(mom) - 1
    out = pd.Series("sideways", index=index.index, dtype=object)
    out[above & (m > 0)] = "bull"
    out[~above & (m < 0)] = "bear"
    out[index.rolling(ma).mean().isna() | m.isna()] = None
    return out


def risk_on(index: pd.Series) -> pd.Series:
    """True when the trend regime is bull or sideways-above-average; used by the regime-aware strategy."""
    t = trend_regime(index)
    return (t != "bear") & t.notna()


def hmm_regimes(index: pd.Series, n_states: int = 3, train_frac: float = 0.6, seed: int = 0) -> dict:
    from hmmlearn.hmm import GaussianHMM

    r = index.pct_change().dropna()
    if len(r) < 3 * MIN_HISTORY_DAYS:
        return {"available": False, "reason": "not enough history for a hidden Markov model"}
    n_train = int(len(r) * train_frac)
    X = r.to_numpy()[:, None] * 100
    model = GaussianHMM(n_components=n_states, covariance_type="diag", n_iter=200, random_state=seed)
    model.fit(X[:n_train])
    means, var = model.means_[:, 0], model.covars_[:, 0, 0]
    # A Gaussian HMM on daily returns separates states mainly by VARIANCE, not by trend, so states are named by their
    # fitted volatility (calm / moderate / turbulent). Calling them bull or bear would misdescribe what was estimated.
    order = np.argsort(var)
    names = {int(order[0]): "calm", int(order[-1]): "turbulent"}
    for k in range(n_states):
        names.setdefault(k, "moderate")
    A = model.transmat_
    alpha = model.startprob_.copy()
    states, probs = [], []
    for x in X:
        alpha = (alpha @ A) * _norm_pdf(x[0], loc=means, scale=np.sqrt(var))
        s = alpha.sum()
        alpha = alpha / s if s > 0 else np.full(n_states, 1 / n_states)
        states.append(int(np.argmax(alpha)))
        probs.append(alpha.copy())
    lab = pd.Series([names[s] for s in states], index=r.index)
    p = pd.DataFrame(probs, index=r.index, columns=[names[k] if list(names.values()).count(names[k]) == 1 else f"{names[k]}_{k}" for k in range(n_states)])
    return {
        "available": True, "labels": lab, "probabilities": p, "train_end": r.index[n_train - 1],
        "state_params": {names[k]: {"mean_daily_pct": float(means[k]), "vol_daily_pct": float(np.sqrt(var[k]))} for k in range(n_states)},
        "labelled_by": "fitted volatility",
        "note": f"Parameters fitted on data to {r.index[n_train - 1].date()}; later labels use filtered (forward-only) probabilities.",
    }


def gmm_regimes(index: pd.Series, n_states: int = 3, seed: int = 0) -> pd.Series:
    """DESCRIPTIVE ONLY: Gaussian mixture on 21-day return and volatility, fitted on the full sample (hindsight)."""
    from sklearn.mixture import GaussianMixture

    r = index.pct_change()
    feat = pd.DataFrame({"ret": index.pct_change(21), "vol": r.rolling(21).std() * np.sqrt(TRADING_DAYS)}).dropna()
    g = GaussianMixture(n_components=n_states, covariance_type="full", random_state=seed, n_init=3).fit(feat)
    lab = g.predict(feat)
    order = np.argsort(g.means_[:, 0])
    names = {int(order[0]): "bear", int(order[-1]): "bull"}
    for k in range(n_states):
        names.setdefault(k, "sideways")
    return pd.Series([names[x] for x in lab], index=feat.index)


def regime_stats(index: pd.Series, labels: pd.Series) -> list[dict]:
    """Return statistics per regime, using each day's return under the PREVIOUS day's label.

    A label at date t is known at the close of t, so the return that earned it must not be counted as the regime's
    return; using the next day's return removes that look-ahead (it makes bull vs bear gaps look smaller, which is
    the honest picture)."""
    r = index.pct_change()
    lab = labels.reindex(r.index).shift(1)
    out = []
    for name in sorted(lab.dropna().unique()):
        mask = lab == name
        rr = r[mask].dropna()
        if len(rr) < 20:
            continue
        runs = (lab != lab.shift()).cumsum()[mask]
        lengths = runs.groupby(runs).size()
        out.append({
            "regime": name, "days": int(mask.sum()), "share": float(mask.mean()),
            "annualised_return": float(((1 + rr).prod() ** (TRADING_DAYS / len(rr)) - 1) * 100),
            "annualised_vol": float(rr.std(ddof=1) * np.sqrt(TRADING_DAYS) * 100),
            "avg_duration_days": float(lengths.mean()), "episodes": len(lengths),
        })
    return out


def transition_matrix(labels: pd.Series) -> dict:
    lab = labels.dropna()
    states = sorted(lab.unique())
    m = pd.crosstab(lab.shift(1).iloc[1:], lab.iloc[1:], normalize="index").reindex(index=states, columns=states).fillna(0)
    return {"states": states, "matrix": m.round(4).to_numpy().tolist()}
