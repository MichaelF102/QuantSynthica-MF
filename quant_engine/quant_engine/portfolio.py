"""Portfolio construction: estimation, constrained optimisers, frontier, risk decomposition, out-of-sample check.

Honesty rules baked in
- Historical mean returns are a very noisy estimate of expected returns. They are shrunk toward the cross-sectional
  mean (`shrink`), and every optimisation reports an out-of-sample hold-out comparison with equal weight.
- Covariance is Ledoit-Wolf shrunk, checked for conditioning, and repaired if not positive definite.
- Every result lists its assumptions and warnings; solver failures are reported, never silently replaced.
- Long-only, fully invested (weights sum to 1). Constraints: per-fund bounds, maximum number of funds, group limits.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

PORTFOLIO_VERSION = "portfolio-1.0.0"
TRADING_DAYS = 252
MIN_OBS = 250
MAX_FUNDS = 40



def minimize(*a, **k):
    from scipy.optimize import minimize as _m  # imported on first use: ~40 MB the API does not need until someone optimises

    return _m(*a, **k)


def linprog(*a, **k):
    from scipy.optimize import linprog as _l

    return _l(*a, **k)


class OptimisationError(ValueError):
    pass


@dataclass(frozen=True)
class Limits:
    """Long-only constraints. `groups` = (member indices, min share, max share), e.g. a category or asset-tier limit."""

    min_w: float = 0.0
    max_w: float = 1.0
    max_funds: int | None = None
    groups: tuple[tuple[tuple[int, ...], float, float], ...] = ()

    def check(self, n: int) -> None:
        if not 0 <= self.min_w <= self.max_w <= 1:
            raise OptimisationError("fund limits must satisfy 0 <= min <= max <= 1")
        if self.min_w * n > 1 + 1e-9:
            raise OptimisationError(f"minimum weight {self.min_w:.0%} x {n} funds exceeds 100%")
        if self.max_w * n < 1 - 1e-9:
            raise OptimisationError(f"maximum weight {self.max_w:.0%} x {n} funds cannot reach 100%")
        for members, lo, hi in self.groups:
            if lo > hi or not members:
                raise OptimisationError("invalid group limit")
            if hi < self.min_w * len(members) - 1e-9 or lo > self.max_w * len(members) + 1e-9:
                raise OptimisationError("a group limit conflicts with the per-fund limits")
        if self.max_funds is not None and self.max_funds * self.max_w < 1 - 1e-9:
            raise OptimisationError(f"holding at most {self.max_funds} funds at {self.max_w:.0%} each cannot reach 100%")


# --------------------------------------------------------------------------- estimation
@dataclass
class Estimates:
    codes: list[str]
    mu: np.ndarray  # annualised expected return (decimal), after shrinkage
    mu_hist: np.ndarray
    cov: np.ndarray  # annualised covariance
    n_obs: int
    start: str
    end: str
    condition_number: float
    shrinkage_cov: float
    warnings: list[str] = field(default_factory=list)


def ledoit_wolf(X: np.ndarray) -> tuple[np.ndarray, float]:
    """Ledoit-Wolf shrinkage of the sample covariance toward a scaled identity (the estimator scikit-learn implements).
    Written out in numpy so the portfolio tools do not need scikit-learn; a test pins it to scikit-learn's output."""
    X = np.asarray(X, dtype=float)
    n, p = X.shape
    Xc = X - X.mean(axis=0)
    emp = Xc.T @ Xc / n
    mu = np.trace(emp) / p
    X2 = Xc ** 2
    beta_ = np.sum(X2.T @ X2)
    delta_ = np.sum((Xc.T @ Xc) ** 2) / n ** 2
    beta = (beta_ / n - delta_) / (p * n)
    delta = (delta_ - 2.0 * mu * np.trace(emp) + p * mu ** 2) / p
    beta = min(beta, delta)
    shrink = 0.0 if beta == 0 else beta / delta
    return (1 - shrink) * emp + shrink * mu * np.eye(p), float(shrink)


def estimate(rets: pd.DataFrame, lookback_days: int = 1096, shrink: float = 0.5) -> Estimates:
    """Annualised mean (shrunk) and Ledoit-Wolf covariance from the common dates of `rets` (daily simple returns)."""
    if rets.shape[1] < 2:
        raise OptimisationError("select at least two funds")
    if rets.shape[1] > MAX_FUNDS:
        raise OptimisationError(f"at most {MAX_FUNDS} funds are supported")
    end = rets.index.max()
    w = rets.loc[rets.index > end - pd.Timedelta(days=lookback_days)].dropna()
    if len(w) < MIN_OBS:
        raise OptimisationError(f"only {len(w)} common daily observations in the lookback; at least {MIN_OBS} are needed "
                                "(a selected fund may be too new)")
    X = w.to_numpy()
    lw_cov, lw_shrink = ledoit_wolf(X)
    cov = lw_cov * TRADING_DAYS
    cov = (cov + cov.T) / 2
    warns: list[str] = []
    eig = np.linalg.eigvalsh(cov)
    if eig.min() <= 1e-12:
        cov = cov + np.eye(len(cov)) * (abs(eig.min()) + 1e-8)  # nearest repair: tiny ridge
        warns.append("Covariance was not positive definite and was repaired with a small ridge.")
    cond = float(np.linalg.cond(cov))
    if cond > 1e6:
        warns.append(f"Covariance is ill-conditioned (condition number {cond:.1e}); funds are nearly collinear and weights may be unstable.")
    mu_hist = X.mean(axis=0) * TRADING_DAYS
    mu = (1 - shrink) * mu_hist + shrink * mu_hist.mean()
    if shrink < 0.25:
        warns.append("Little shrinkage of historical mean returns: maximum-Sharpe weights will be dominated by recent winners.")
    if len(w) < 3 * rets.shape[1] * 10:
        warns.append("Few observations relative to the number of funds: estimates are noisy.")
    return Estimates(list(w.columns), mu, mu_hist, cov, len(w), str(w.index[0].date()), str(w.index[-1].date()), cond,
                     float(lw_shrink), warns)


# --------------------------------------------------------------------------- helpers
def stats(w: np.ndarray, mu: np.ndarray, cov: np.ndarray, rf: float = 0.0) -> dict[str, float]:
    ret = float(w @ mu)
    vol = float(math.sqrt(max(w @ cov @ w, 0.0)))
    return {"expected_return": ret * 100, "volatility": vol * 100, "sharpe": (ret - rf) / vol if vol > 1e-12 else float("nan")}


def _bounds(n: int, lim: Limits):
    return [(lim.min_w, lim.max_w)] * n


def _cons(n: int, lim: Limits):
    cons = [{"type": "eq", "fun": lambda w: w.sum() - 1.0, "jac": lambda w: np.ones(n)}]
    for members, lo, hi in lim.groups:
        idx = list(members)
        cons.append({"type": "ineq", "fun": lambda w, idx=idx, lo=lo: w[idx].sum() - lo})
        cons.append({"type": "ineq", "fun": lambda w, idx=idx, hi=hi: hi - w[idx].sum()})
    return cons


def _start(n: int, lim: Limits) -> np.ndarray:
    w = np.full(n, 1.0 / n)
    return np.clip(w, lim.min_w, lim.max_w)


def _solve(fun, n: int, lim: Limits, name: str, x0: np.ndarray | None = None, jac=None) -> np.ndarray:
    lim.check(n)
    res = minimize(fun, x0 if x0 is not None else _start(n, lim), jac=jac, bounds=_bounds(n, lim), constraints=_cons(n, lim),
                   method="SLSQP", options={"maxiter": 500, "ftol": 1e-11})
    if not res.success and not _feasible(res.x, lim):
        raise OptimisationError(f"{name}: solver did not converge ({res.message}); relax the constraints")
    w = np.clip(res.x, lim.min_w, lim.max_w)
    return w / w.sum()


def _feasible(w: np.ndarray, lim: Limits, tol: float = 1e-6) -> bool:
    if abs(w.sum() - 1) > tol or (w < lim.min_w - tol).any() or (w > lim.max_w + tol).any():
        return False
    return all(lo - tol <= w[list(m)].sum() <= hi + tol for m, lo, hi in lim.groups)


def _cardinality(solve, n: int, lim: Limits) -> np.ndarray:
    """Heuristic for 'hold at most k funds': solve, keep the k largest weights, re-solve on that subset."""
    w = solve(np.arange(n))
    k = lim.max_funds
    if k is None or (w > 1e-6).sum() <= k:
        return w
    keep = np.argsort(-w)[:k]
    sub = solve(np.sort(keep))
    out = np.zeros(n)
    out[np.sort(keep)] = sub
    return out


# --------------------------------------------------------------------------- optimisers
def _sub_limits(lim: Limits, keep: np.ndarray) -> Limits:
    pos = {int(k): i for i, k in enumerate(keep)}
    groups = []
    for members, lo, hi in lim.groups:
        m = tuple(pos[i] for i in members if i in pos)
        if m:
            groups.append((m, lo, hi))
    return Limits(lim.min_w, lim.max_w, None, tuple(groups))


def equal_weight(n: int, lim: Limits) -> np.ndarray:
    lim.check(n)
    w = np.full(n, 1.0 / n)
    if not _feasible(w, lim):
        raise OptimisationError("equal weight violates the constraints; use another method or relax the limits")
    return w


def min_variance(cov: np.ndarray, lim: Limits) -> np.ndarray:
    def solve(idx):
        c = cov[np.ix_(idx, idx)]
        sub = _sub_limits(lim, idx) if len(idx) < len(cov) else lim
        return _solve(lambda w: w @ c @ w, len(idx), sub, "minimum variance", jac=lambda w: 2 * c @ w)
    return _cardinality(solve, len(cov), lim)


def max_sharpe(mu: np.ndarray, cov: np.ndarray, rf: float, lim: Limits) -> np.ndarray:
    def solve(idx):
        m, c = mu[idx], cov[np.ix_(idx, idx)]
        sub = _sub_limits(lim, idx) if len(idx) < len(cov) else lim

        def neg(w):
            v = math.sqrt(max(w @ c @ w, 1e-14))
            return -(w @ m - rf) / v
        return _solve(neg, len(idx), sub, "maximum Sharpe")
    return _cardinality(solve, len(cov), lim)


def risk_parity(cov: np.ndarray, lim: Limits) -> np.ndarray:
    """Equal risk contribution: minimise the dispersion of w_i * (cov w)_i."""
    def solve(idx):
        c = cov[np.ix_(idx, idx)]
        sub = _sub_limits(lim, idx) if len(idx) < len(cov) else lim

        def obj(w):
            rc = w * (c @ w)
            tot = rc.sum()
            return float(((rc / tot - 1.0 / len(w)) ** 2).sum()) if tot > 0 else 1e6
        # start from inverse-volatility weights, a close approximation
        inv = 1 / np.sqrt(np.diag(c))
        x0 = np.clip(inv / inv.sum(), sub.min_w, sub.max_w)
        return _solve(obj, len(idx), sub, "risk parity", x0=x0 / x0.sum())
    return _cardinality(solve, len(cov), lim)


def min_cvar(scenarios: np.ndarray, lim: Limits, alpha: float = 0.95) -> tuple[np.ndarray, float]:
    """Rockafellar-Uryasev linear programme on historical scenarios (daily returns, T x n). Returns (weights, daily CVaR)."""
    T, n = scenarios.shape
    lim.check(n)
    # variables: w (n), VaR zeta (1), shortfalls u (T). minimise zeta + 1/((1-alpha)T) sum u
    c = np.concatenate([np.zeros(n), [1.0], np.full(T, 1.0 / ((1 - alpha) * T))])
    A_ub = np.hstack([-scenarios, -np.ones((T, 1)), -np.eye(T)])  # -r.w - zeta - u <= 0
    b_ub = np.zeros(T)
    rows, rhs = [], []
    for members, lo, hi in lim.groups:
        r = np.zeros(n + 1 + T)
        r[list(members)] = 1
        rows.append(-r); rhs.append(-lo)
        rows.append(r); rhs.append(hi)
    if rows:
        A_ub = np.vstack([A_ub, np.array(rows)])
        b_ub = np.concatenate([b_ub, rhs])
    A_eq = np.concatenate([np.ones(n), [0.0], np.zeros(T)])[None, :]
    bounds = [(lim.min_w, lim.max_w)] * n + [(None, None)] + [(0, None)] * T
    res = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=[1.0], bounds=bounds, method="highs")
    if not res.success:
        raise OptimisationError(f"CVaR optimisation failed: {res.message}")
    w = np.clip(res.x[:n], lim.min_w, lim.max_w)
    w = w / w.sum()
    cvar = float(res.fun)  # expected loss beyond VaR (positive number)
    return w, cvar


def efficient_frontier(mu: np.ndarray, cov: np.ndarray, lim: Limits, points: int = 25) -> list[dict]:
    """Minimum-variance portfolios for target returns between the minimum-variance return and the best feasible return."""
    n = len(mu)
    lim.check(n)
    wmin = min_variance(cov, Limits(lim.min_w, lim.max_w, None, lim.groups))
    lo = float(wmin @ mu)
    res = linprog(-mu, A_eq=np.ones((1, n)), b_eq=[1.0], bounds=_bounds(n, lim),
                  A_ub=np.array([[1 if i in m else 0 for i in range(n)] for m, _, _ in lim.groups] +
                                [[-1 if i in m else 0 for i in range(n)] for m, _, _ in lim.groups]) if lim.groups else None,
                  b_ub=np.array([hi for _, _, hi in lim.groups] + [-lo_ for _, lo_, _ in lim.groups]) if lim.groups else None,
                  method="highs")
    if not res.success:
        raise OptimisationError("could not find the highest-return feasible portfolio")
    hi = float(-res.fun)
    out = []
    prev = None
    for target in np.linspace(lo, hi, points):
        cons = _cons(n, lim) + [{"type": "ineq", "fun": lambda w, t=target: w @ mu - t + 1e-9}]
        r = minimize(lambda w: w @ cov @ w, prev if prev is not None else wmin, jac=lambda w: 2 * cov @ w, bounds=_bounds(n, lim),
                     constraints=cons, method="SLSQP", options={"maxiter": 300, "ftol": 1e-11})
        if not r.success and not _feasible(r.x, lim):
            continue
        w = r.x / r.x.sum()
        prev = w
        out.append({"weights": w.tolist(), **stats(w, mu, cov)})
    return out


def black_litterman(cov: np.ndarray, w_ref: np.ndarray, views: list[tuple[np.ndarray, float]], *, risk_aversion: float = 2.5,
                    tau: float = 0.05, view_uncertainty: float = 0.5) -> np.ndarray:
    """Posterior expected returns. Prior = reverse optimisation of the reference weights; `views` are (P row, Q) absolute or
    relative views on annual return. Needs explicit user views: without them the posterior equals the prior."""
    pi = risk_aversion * cov @ w_ref
    if not views:
        return pi
    P = np.array([v[0] for v in views])
    Q = np.array([v[1] for v in views])
    omega = np.diag(np.diag(P @ (tau * cov) @ P.T)) * (1 / max(view_uncertainty, 1e-6))
    inv = np.linalg.inv(np.linalg.inv(tau * cov) + P.T @ np.linalg.inv(omega) @ P)
    return inv @ (np.linalg.inv(tau * cov) @ pi + P.T @ np.linalg.inv(omega) @ Q)


# --------------------------------------------------------------------------- analytics
def risk_decomposition(w: np.ndarray, cov: np.ndarray) -> dict:
    port_var = float(w @ cov @ w)
    marginal = cov @ w
    contrib = w * marginal / port_var if port_var > 0 else np.zeros_like(w)
    vols = np.sqrt(np.diag(cov))
    return {
        "risk_contribution_pct": (contrib * 100).tolist(),
        "diversification_ratio": float((w @ vols) / math.sqrt(port_var)) if port_var > 0 else None,
        "effective_number_of_funds": float(1 / (w**2).sum()),
        "herfindahl": float((w**2).sum()),
    }


def portfolio_nav(panel: pd.DataFrame, weights: dict[str, float], rebalance: str = "M") -> pd.Series:
    """Index (base 100) of a portfolio held at target weights, rebalanced at month ends ('M'), quarter ends ('Q'),
    year ends ('Y') or never ('none', buy and hold). Starts on the first date every fund has a NAV."""
    cols = list(weights)
    px = panel[cols].dropna()
    if len(px) < 30:
        raise OptimisationError("selected funds have too little overlapping history")
    w = np.array([weights[c] for c in cols], dtype=float)
    w = w / w.sum()
    rets = px.pct_change().dropna().to_numpy()
    idx = px.index[1:]
    value = 100.0
    hold = w * value
    out = []
    period = {"M": idx.to_period("M"), "Q": idx.to_period("Q"), "Y": idx.to_period("Y")}.get(rebalance)
    for i, r in enumerate(rets):
        hold = hold * (1 + r)
        value = hold.sum()
        out.append(value)
        if period is not None and (i + 1 == len(rets) or period[i + 1] != period[i]):
            hold = w * value
    s = pd.Series(out, index=idx)
    return pd.concat([pd.Series([100.0], index=[px.index[0]]), s])


# --------------------------------------------------------------------------- out-of-sample check
def holdout_check(rets: pd.DataFrame, solver, lim: Limits, holdout_days: int = 365, lookback_days: int = 1096, shrink: float = 0.5,
                  rf: float = 0.0) -> dict:
    """Fit on data BEFORE the hold-out window, then compare the optimised and equal-weight portfolios on the hold-out.

    `solver(est, lim) -> weights` is the same function used for the final answer. A weighting that looks good only
    in-sample and does worse than equal weight out-of-sample is a sign of overfitting."""
    end = rets.index.max()
    cut = end - pd.Timedelta(days=holdout_days)
    train, test = rets.loc[:cut], rets.loc[rets.index > cut].dropna()
    if len(test) < 60:
        return {"available": False, "reason": "not enough data after the cut-off for a hold-out"}
    try:
        est = estimate(train, lookback_days, shrink)
    except OptimisationError as exc:
        return {"available": False, "reason": f"not enough data before the cut-off: {exc}"}
    cols = est.codes
    w = solver(est, lim)
    ew = np.full(len(cols), 1 / len(cols))  # plain equal weight: a yardstick, deliberately not subject to the user's limits
    t = test[cols].to_numpy()

    def perf(weights):
        r = t @ weights
        ann = (1 + r).prod() ** (TRADING_DAYS / len(r)) - 1
        vol = r.std(ddof=1) * math.sqrt(TRADING_DAYS)
        return {"return": float(ann * 100), "volatility": float(vol * 100), "sharpe": float((ann - rf) / vol) if vol > 1e-12 else None}

    return {"available": True, "fit_end": str(train.index[-1].date()), "holdout_start": str(test.index[0].date()), "holdout_end": str(test.index[-1].date()),
            "observations": int(len(test)), "optimised": perf(w), "equal_weight": perf(ew),
            "note": "One hold-out window is one sample: treat a win or a loss as weak evidence either way."}
