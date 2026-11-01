# Phase 5 progress — Quant scoring, research, regimes, backtesting

Status as of 2026-11-01: **built and verified. Research findings are mostly negative; read "What the evidence says" before relying on the score.**

## Verification
- Tests: data pipeline 47, quant engine 83, backend 63, browser 43 (Phase 2 to 5 specs plus 17 design checks at 375/1280/1920 px) all pass. `tsc` and `eslint` clean.
- NAV store restored with `pipeline rebuild` (21,837,711 rows, identical to before the interruption). Full build `python -m app.cli.quant` completed: **210 monthly dates (May 2009 to Oct 2026), 822 funds, 721 scored**, 50 funds excluded for genuine one-day NAV jumps.
- Remaining lint: 37 minor ruff style warnings (35 need unsafe auto-fixes; left alone).

## What was built
- `quant_engine`: `panel`, `scoring` (score-1.0.0), `research`, `backtest` (backtest-1.0.0), `regime`, `clustering`. Point-in-time tests (changing future data cannot change a past score, trade or regime label), vectorised-vs-scalar equivalence, hand-checked cost accounting, planted-signal and null-signal research tests.
- Backend: tables `fund_scores`, `backtest_runs`; `/api/v1/quant/*` (methodology, groups, scores, score detail, factors, statistics, clusters, regimes, backtests as background jobs with caching and polling); screener fields for the quant score and factor scores.
- Frontend: Quant Research Lab menu and six pages (scoring, factor research, statistical analysis, clustering, regimes, backtesting), a Quant Score tab on every fund, a Quant score column in the Screener.

## What the evidence says (survivors only; today's categories; costs are assumptions)
**Factor research (210 dates, 2009 to 2026).** Rank IC against the next period's peer-relative return:
| Signal | 1M | 3M | 6M | 12M |
|---|---|---|---|---|
| Momentum | 0.090 (t 6.2) | 0.126 (t 4.2) | 0.142 (t 3.9) | 0.128 (n.s.) |
| Performance | 0.062 (t 5.2) | 0.086 (t 4.0) | 0.077 (t 2.1) | 0.047 |
| Composite | 0.053 (t 3.8) | 0.079 (t 3.3) | 0.083 (t 2.2) | 0.062 |
| Consistency | 0.041 | 0.067 | 0.075 | 0.062 |
| Risk-adjusted | 0.033 | 0.045 | 0.045 | 0.021 |
| Downside protection | -0.016 | -0.021 | -0.019 | -0.019 |
At 12 months only 17 independent dates exist, so no t-statistic is meaningful there. Top-quartile funds land in the next year's top quartile 33% of the time (25% by chance). Survivorship bias inflates all of this.

**Backtests (about 12 years, quarterly rebalance, hold 10, Direct plans; benchmark = equal-weighted eligible universe).**
- With the default cost assumptions (0.1% per trade, 1% exit load under 1 year, 3-day delay): **no strategy beats the benchmark**. Equity, difference per year: multi-factor -1.9 pp (t -2.3), quality -2.1 pp (t -2.6), momentum 6M -2.9, momentum 12M -0.8, risk-adjusted momentum +0.7 (t 0.03), consistency -0.2, low volatility -4.7, regime-aware -7.6 (t -3.9). Debt: every strategy is 0.7 to 2.0 pp below.
- With costs set to zero: momentum 12M +1.8 pp, risk-adjusted momentum +2.6 pp, momentum 6M +0.8, consistency +1.2; every 95% interval includes zero. Quality -0.8, multi-factor -0.06 (nothing).
- Rebalancing yearly with costs: all strategies still at or below the benchmark.
- Interpretation: the only plausible edge is momentum, it is statistically indistinguishable from zero and disappears after costs. **The composite score, as weighted, has no demonstrated selection advantage.** Its 15% Downside weight points the wrong way on this sample, which dilutes the momentum signal. Do not present the score as predictive.

**Regimes (equity proxy of Direct equity funds).**
- Trend regime statistics are computed on the day after each label. After correction, bear-labelled periods were followed by +20% a year versus +17% after bull labels: the rule does not time the market here. An earlier version that counted the same day's move showed bull +28% and bear -14%; that was a look-ahead artefact and was removed.
- The hidden Markov model separates states by volatility (calm 63% of days, moderate 35%, turbulent 2%), so states are named by volatility, not bull/bear. The Gaussian mixture is hindsight and descriptive only.

## Corrections made during this phase
- Persistence redefined to the next 12 months' peer-relative return (the first definition showed 63% persistence in pure noise because trailing windows overlap).
- t-statistics withheld with fewer than 10 non-overlapping dates (one was 11 from 3 dates).
- Suspect-NAV check ignores jumps across data holes (it wrongly dropped about 500 funds during a partial load).
- HMM relabelled by volatility; regime statistics lagged one day.

## Not done / deliberately out of scope
- Stability factor (needs AUM history, expense ratios, manager tenure): reported as unavailable; weights renormalised.
- Survivorship-free universe (needs closed and merged schemes), point-in-time categories, licensed benchmark and risk-free series (ADR 005 questions still open), taxes in backtests.
- Weight tuning: not done on purpose. Any change to the 25/25/20/15/10/5 weights must be a new methodology version tested on a held-out period; the current evidence argues for revisiting the Downside weight, but that needs fresh out-of-sample data.
- Mockup tabs without data or scope: style analysis, machine learning, strategy library and saved strategies, factor attribution, model evaluation, strategy comparison view, optimisation (Phase 6).
- Backtests run in a thread inside the API process; a restart loses a running job (no queue yet).
- Build time: scoring takes about 4 s per date, the full history build about 10 to 12 minutes, with no progress display.

## How to rerun
```bash
make up
cd backend
../.venv/bin/python -m app.cli.quant                      # full point-in-time build (10 to 12 min)
../.venv/bin/python -m uvicorn app.main:app --port 8000
cd ../frontend && npm run build && npm run start -- -p 3000
npx playwright test
```
