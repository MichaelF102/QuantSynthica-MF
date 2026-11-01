# Phase 6 — Portfolio Management (Weeks 10–12)

## Engine (`quant_engine/optimization`, `portfolio`)
- Covariance estimation (sample, Ledoit-Wolf shrinkage), numerical-stability handling, condition-number warnings.
- Optimizers: equal weight, min variance, max Sharpe, risk parity / ERC, CVaR (CVXPY), Black-Litterman (only with sufficient inputs), efficient frontier.
- Constraints: fully invested, per-fund min/max, max fund count, category and asset-class limits.
- Analytics: portfolio return/risk, diversification, risk contribution, correlation matrix.
- Simulators: SIP, lump sum, SWP, inflation-adjusted; **historical simulation** vs **hypothetical projection** always labelled separately; sensitivity analysis.
- Rebalancing: drift, thresholds, suggested trades, exit-load awareness.
- Stress testing: historical crisis windows (2008 if history permits, 2020, etc.); window availability depends on fund history.

## Backend
Endpoints `/portfolios`, `/portfolios/optimize` (job IDs: POST → 202 → poll `/jobs/{id}`); Redis queue + worker; saved portfolios in PG.

## Frontend
Portfolio Builder, Analytics, Optimization (with assumptions panel and warnings), SIP/SWP, Rebalancing, Stress Testing, portfolio comparison.

## Tests
Weights sum to 1 ± tolerance; constraints satisfied; infeasible constraints return clear errors; optimiser vs analytic solutions on toy cases.

## Gate
Constraints hold, assumptions displayed, historical analysis uses only information available at the time.

---

## Status (2026-11-01): built and verified

Details and caveats: `phase6-progress.md`. Deviations from the plan above, chosen deliberately:
- **No job queue or Postgres-saved portfolios.** Optimisation of up to 40 funds takes well under a second once the NAV panel is cached, so endpoints are synchronous (`/api/v1/portfolio/{analyze,optimize,simulate,rebalance,stress,funds}`). Saved portfolios live in the browser (localStorage) because there are no accounts yet.
- **Portfolio comparison view** is not built.
- Only Growth schemes with a confirmed NAV link can be held (IDCW NAVs exclude payouts).
