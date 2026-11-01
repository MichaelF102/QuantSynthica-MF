# Phase 2 — Discover Pages on Snapshot Data (Weeks 3–5)

Runs in parallel with Phase 3. Uses only data already in Postgres.

## Principles
- Every number from the API; no hardcoded demo values.
- Unavailable widgets render a "needs NAV data" / "data not available" state, not fake numbers.
- Aggregates dedupe by `base_fund` where size is involved (Net Assets repeats across share classes).
- Exclude quarantined and discontinued rows from rankings by default (toggle available).

## 1. Market Overview
Fields available now: counts, tier/category distribution, YTD/3M/1Y/3Y/5Y returns, `*_cat_pct`, Net Assets, AMC.
- KPI tiles: funds, AMCs, categories, average 1Y return (median shown too).
- Category return heatmap (YTD, 3M, 1Y, 3Y, 5Y), tier distribution, category counts.
- Top performers by horizon (peer-group aware, minimum-history caveat).
- Top funds by AUM using deduplicated Net Assets, with coverage shown ("68% of funds have AUM").
- Market breadth: share of schemes with a positive return per horizon, and above their 50-day / 200-day average, by tier. (Changed from `*_cat_pct > 50`: a within-category percentile is ~50% by construction, so it carries no information.)
- AMC leaderboard: median category-percentile per AMC, minimum fund count threshold (not best-fund ranking).
- Not available yet: net flows, AUM trend, "vs last month" deltas. Omit or show placeholder state.

## 2. Fund Screener
- Filter builder: AMC, category, tier, plan, option, AUM, returns, category percentiles/z-scores, range position, price vs 50/200-day, trend flags, insurer/discontinued toggles.
- AND/OR groups, sorting, server-side pagination, URL-persisted state, reset, CSV export, saved screens (local until auth).
- Tabs: All / Equity / Debt / Hybrid / Tax Saving (ELSS) / Custom. Quant Screener tab visible but gated until scores exist.
- Backend: `POST /api/v1/screener` taking a validated filter AST; compile to parameterised SQL (no string concatenation).

## 3. Fund Explorer (`/funds/[id]`)
- Header: name, AMC, category, plan/option badges, price, change %, AUM, 1Y/3Y/5Y returns.
- Tabs live now: Overview, Performance (snapshot returns), NAV Analysis (price vs 50/200, 52-week range).
- Tabs gated with explicit states: Risk & Returns, Portfolio Holdings, Asset Allocation, Benchmark, Fund Manager, Quant Score, AI Research.
- Sibling share classes panel (via `base_fund`).

## 4. Fund Comparison
Up to 5 funds; side-by-side table, return bars, category percentile comparison, 52-week range bars. Warn when comparing across categories or plans.

## Tests / Gate
Playwright smoke tests per page; API contract tests; screener unit tests for AND/OR and null handling (null never matches a numeric condition); empty/error/missing-data states visible. Gate: all pages data-driven, filters combine correctly, production build passes.

## Status (2026-10-31)
Implemented: `/overview`, `/screener` (filter tree API + builder, tabs, saved screens in browser storage, CSV export, compare selection), `/funds/[id]` tabs (Overview, Performance, NAV Analysis live; others gated with reasons), `/comparison`. Backend tests: 38. Browser tests (Playwright, system Chrome): 8.
Not done: server-side saved screens (needs auth, Phase 7), screener Analytics/Distribution/Correlation/Overlap tabs, nested groups in the builder UI (API supports depth 3).
