# Phase 4 — Quant Engine Part 1: Performance & Risk (Weeks 6–8)

Can start on synthetic data before Phase 3 finishes.

## Package: `quant_engine/` (pure Python, no FastAPI/DB)
Dependencies: numpy, pandas, scipy, statsmodels, (arch optional). Typed interfaces; every result is a dataclass containing `value`, `methodology_version`, `window_start`, `window_end`, `observations`, `coverage`, `data_asof`, `conventions` (frequency, annualisation factor, risk-free source, benchmark id).

## Modules
- `common/`: calendars, return construction (simple vs log), resampling, alignment of fund & benchmark series, annualisation constants (252 trading days for daily; document it).
- `performance/`: absolute return, CAGR, annualised return, rolling returns (1Y/3Y/5Y), calendar returns, excess return, tracking error, information ratio, up/down capture, category percentile, persistence.
- `risk/`: volatility (annualised, rolling), Sharpe, Sortino, Calmar, max drawdown + duration + recovery, beta, alpha, downside deviation, historical VaR, parametric VaR, CVaR, skew, kurtosis. GARCH/EGARCH optional module behind an extra.

## Backend & UI
- Service layer calls the engine; results cached in Redis; stored in gold tables keyed by (scheme, metric, window, methodology_version).
- Endpoints: `/performance/{id}`, `/risk/{id}`.
- Frontend: Performance Analytics and Risk Analytics pages; enable Fund Explorer tabs (Performance, Risk & Returns, NAV Analysis, Benchmark). Charts: cumulative, rolling, calendar, drawdown, rolling vol, risk-return scatter. Reuse a single chart component set.

## Tests
- Reference calculations (hand-computed and an independent implementation) for every formula.
- Synthetic series: constant returns, all-negative, missing periods, extreme drawdown, benchmark underperformance, short history.
- Property tests (drawdown ≤ 0, vol ≥ 0, beta of series vs itself = 1).

## Gate
All formulas pass reference tests; outputs carry methodology version/window/coverage; pages show real data for mapped funds and clear "unmapped" state otherwise.

## Status (2026-10-31)
**Built:** `quant_engine` (common, performance, risk, benchmark, analysis; 48 tests including hand-computed and loop-based reference calculations, constant/negative/gap/extreme-drawdown cases), `/api/v1/analytics/{id}` and `/analytics/compare`, batch `scheme_metrics` (872 Growth schemes, 115 peer groups, percentiles), Screener fields for NAV-derived metrics, Fund Explorer tabs (Performance, NAV Analysis, Risk & Returns, Benchmark Analysis), `/performance` and `/risk` pages. All outputs carry methodology version `perf-risk-1.0.0`, window, observation count and coverage.

**Validation on real data:** engine YTD vs source YTD across 742 funds: median error 0.003 pp (99.7% within 0.1 pp); 3M: 0.002 pp.

**Decisions and substitutes (no licensed data connected)**
- Benchmark = equal-weighted average of comparable funds (same category, plan, Growth), excluding the fund itself; today's survivors only. Always labelled; not an index.
- Risk-free = median daily return of confirmed overnight and liquid Growth funds. A proxy, not an official rate.
- Growth options only. IDCW NAVs exclude distributions, so analytics are refused with a reason.
- Guards found on real data: a single-day NAV move above 25% (UTI Liquid: -90% on 2026-06-20) makes affected windows unavailable and removes that fund from peer indices; Sharpe/Sortino/beta are withheld when volatility is under 0.5% p.a. (money-market-like funds).

**Not done:** GARCH/EGARCH, Monte Carlo VaR, stress-test scenarios, performance attribution (needs holdings), upside/downside capture from daily data, rolling-correlation and rolling-beta charts, Redis caching (in-process LRU only), Direct vs Regular cost analysis (needs expense ratios), IDCW total return (needs distributions), benchmark TRI and an official risk-free series.
