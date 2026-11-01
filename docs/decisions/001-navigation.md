# ADR 001 — Navigation

Status: **Proposed** (needs your sign-off)

## Context
Mockups use a 7-item top bar: Market Overview · Fund Explorer · Screener · Analysis · Quant Research Lab · Portfolios · Insights. The blueprint defines 5 groups / 22 pages. Several mockup pages (AMC & Manager Intelligence, Market Regime, AI Assistant, Reports & Watchlists, Fund Comparison) are not clearly anchored in the top bar, and the highlighted tab on those mockups is inconsistent (e.g. Reports shows "Fund Explorer" active).

## Decision
Keep the mockup's **top bar** (matches the visual design) and map the 22 pages into it using a dropdown/sub-nav per item:

| Top-bar item | Pages |
|---|---|
| Market Overview | Market Overview |
| Fund Explorer | Fund Explorer (search + detail), Fund Comparison |
| Screener | Fund Screener (+ analytics tabs, saved screens) |
| Analysis | Performance Analytics, Risk Analytics, AMC & Manager Intelligence |
| Quant Research Lab | Fund Scoring, Factor Research, Statistical Analysis, Clustering, Regime Analysis, Strategy Backtesting |
| Portfolios | Builder, Analytics, Optimization, SIP/SWP, Rebalancing, Stress Testing |
| Insights | AI Research Assistant, Research Reports, Watchlists & Alerts |

URL scheme mirrors the blueprint's repo structure (`/overview`, `/screener`, `/funds/[id]`, `/comparison`, `/performance`, `/risk`, `/amc`, `/quant/*`, `/portfolio/*`, `/ai-research`, `/reports`, `/watchlists`).

## Consequences
- Matches mockups; fewer top-level items than the blueprint's sidebar.
- Pages not available yet render a visible "Coming in Phase N / needs NAV data" state rather than being hidden, so the navigation is stable.
- If you prefer the blueprint's left sidebar, only the shell changes, not routes.
