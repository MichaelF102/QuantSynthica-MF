# Phase 6 progress — Portfolio management

Status as of 2026-11-01: **built and verified.**

## Verification
- Tests: data pipeline 47, quant engine 112, backend 81 (17 new Phase 6 API tests on a synthetic universe), browser 56 (13 new in `e2e/phase6.spec.ts`, incl. overflow at 375/1280/1920 px). `tsc` and `eslint` clean. Ruff: a few style warnings remain (RUF046 and similar).

## What was built
- `quant_engine/portfolio.py` (portfolio-1.0.0): Ledoit-Wolf covariance, shrunk mean returns, minimum variance, maximum Sharpe, risk parity, minimum CVaR (linear programme), efficient frontier, Black-Litterman (only with explicit views, equal-weight prior), risk decomposition, rebalanced portfolio NAV, cardinality limit, out-of-sample hold-out check. Reference tests against closed forms.
- `quant_engine/simulate.py` (simulate-1.0.0): XIRR, lump sum, SIP (step-up, inflation), SWP, rolling SIP outcomes and SWP survival (historical); lognormal and bootstrap projections and beta shock scenarios (hypothetical); stress episodes detected from the data; rebalance planner with costs and exit loads.
- Backend `/api/v1/portfolio/*`, validation with explicit 422 reasons.
- Frontend `/portfolio/{builder,optimization,sip-swp,rebalancing,stress-testing}`, Portfolios menu, shared fund picker (selection lives in the URL, saved portfolios in the browser).

## Honest limits
- Expected returns are shrunk historical means, not forecasts. Each optimisation reports a 12-month out-of-sample check against equal weight and warns when equal weight won.
- Historical outputs and hypothetical projections are labelled separately on every result.
- The stress market proxy is survivors only; funds younger than an episode show "not available", never an estimate.
- Beta shocks understate crisis losses (stated on the page).
- Taxes are not modelled. Exit loads use a single user-entered percentage.
- Not done: portfolio comparison view, server-side saved portfolios, background jobs, factor attribution.
