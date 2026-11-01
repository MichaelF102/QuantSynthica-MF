# Screen → Data Map

Source: 19 mockups in `ui/` (12 screens). Review date 2026-10-31.

**Status codes**
- **A** — available now from `yahoo_funds_clean.csv`
- **A\*** — available now but needs care (deduplicate, null handling, derivation)
- **NAV** — needs historical NAV (Phase 3 AMFI pipeline)
- **BM** — needs benchmark TRI history
- **RF** — needs risk-free rate
- **H** — needs portfolio holdings
- **EXP / AUMH / MGR** — needs expense ratio / AUM history / manager data
- **FLOW** — needs fund-flow data (no source identified)
- **MACRO** — needs macro/market indicators
- **Q** — produced by our own quant engine (Phase 4–5) on top of NAV
- **APP** — user/application data (auth, saved items)
- **AI** — LLM feature (Phase 7)
- **✗** — no realistic source; drop or redesign

## Cross-cutting findings
1. **Mockup figures are placeholders and conflict with the CSV.** Examples: screener plan counts (Direct 1,842 / Regular 1,134 vs CSV 1,557 / 808), Growth 2,156 vs CSV 1,026, "Total AUM ₹27.4T", US funds (Vanguard, SPDR, ProShares) in Market Overview. None may be copied.
2. **Dates in mockups** (Apr 24 2025) are illustrative. The CSV snapshot date is unknown.
3. **Almost every chart beyond tables/heatmaps/distributions needs NAV history.** Only Phase 2 pages are CSV-only.
4. **Benchmark = Nifty 500 TRI** is hard-coded in mockups; the real benchmark must come from category → benchmark mapping (BM, licence check).
5. **Mockup nav** has 7 top-bar items: Market Overview · Fund Explorer · Screener · Analysis · Quant (Models → renamed "Quant Research Lab" on later screens) · Portfolios · Insights. Several pages (AMC, Regime, AI, Reports) have no clear top-bar home. See `docs/decisions/001-navigation.md`.
6. **Fund images/logos and manager photos** are not available from any source: use initials/AMC monogram placeholders.

---

## 01 Market Overview (`01_Market_Overview1/2`) — Phase 2
| Widget | Fields | Status | Notes |
|---|---|---|---|
| KPI: Total Net Assets | Net Assets | **A\*** | 32% null; sum by `base_fund` not row; show coverage %. "vs last month" delta ✗ (AUMH). |
| KPI: Number of funds | Symbol | A | 3,351 (or distinct schemes after dedupe; show both). |
| KPI: Avg 1Y return | 1-Year Return | A\* | Show median too; filter quarantined; delta vs last month ✗. |
| KPI: Top performing category | Category, 1Y | A\* | Minimum fund-count threshold per category. |
| KPI: Top inflow category | — | **FLOW** | Drop until a flow source exists. |
| Category performance bars/heatmap (1M…5Y) | Category, YTD/3M/1Y/3Y/5Y | A\* | CSV has no 1M, 6M, 10Y. Show available horizons only. |
| AUM by category donut | Net Assets, Category | A\* | Dedupe; "unknown AUM" slice shown explicitly. |
| AUM Trend / AUM by asset class over time | — | **AUMH** | Drop for Phase 2. |
| Market Trends – category performance lines | — | **NAV** (or category index built from NAV) | Phase 4+. |
| Top 10 performing funds (1Y) | Name, Category, 1Y, Net Assets | A\* | Peer-aware; flag very small/new funds. |
| Top 10 funds by AUM | Net Assets | A\* | Dedupe share classes. |
| Net flows by category | — | **FLOW** | Drop. |
| Market breadth (% outperformed category avg) | `*_cat_pct` | A | Define as cat_pct > 50 (document). Per-tier breadth is available. |
| AMC performance table (Avg 3Y, fund count, AUM) | AMC, 3Y, Net Assets | A\* | Use median category percentile, min fund count; "3Y trend" sparkline ✗ (NAV). |
| Fund count by AMC | AMC | A | |
| Category risk-return scatter (5Y) | 5Y return, volatility | **NAV** | Volatility not in CSV (only `ret_std_1_3_5`, a return dispersion, not volatility). |

## 02 Fund Screener (`02_FundScreener1/2`) — Phase 2 (+ NAV/Q later)
| Widget | Fields | Status | Notes |
|---|---|---|---|
| Header counts, KPI strip | counts, avg 1Y, AUM | A\* | |
| Tabs: All / Equity / Debt / Hybrid / ELSS | asset_tier, Category | A | ELSS = Category "ELSS (Tax Savings)" (117 funds). |
| Tabs: Quant Screener | scores | **Q** | Gated until Phase 5. |
| Tab: Custom Screener / Saved Screens | — | APP | Local storage until auth. |
| Filters: AMC, Category, Plan, Option, Asset class, search | AMC, Category, plan_type, option_type, asset_tier | A | Keep "Unspecified" as a selectable value (975 plan, 415 option). |
| Filter: AUM, 1Y, 3Y returns | Net Assets, returns | A\* | Null never matches numeric conditions. |
| Table cols: AUM, NAV, 3M, 1Y, 3Y CAGR, 5Y CAGR | Net Assets, Price, returns | A\* | "NAV" = Price (Intraday); label as price/NAV. **1M** column ✗ (not in CSV); CAGR labelled as "3Y/5Y Return" — verify whether CSV values are annualised (check against AMFI NAV in Phase 3). |
| Table cols: Sharpe (3Y), Max DD (3Y), Quant Score | — | **Q/NAV** | Show "—" with tooltip until available. |
| Trend (1Y) sparkline | — | **NAV** | Phase 3+. |
| Analytics tab: Return vs Risk, rolling distribution, drawdown | — | **NAV/Q** | |
| Analytics: category allocation by AUM | Net Assets | A\* | |
| Analytics: monthly flows / inflows | — | **FLOW** | Drop. |
| Distribution Charts tab | returns, percentiles | A | Histograms/box plots from CSV are feasible. |
| Correlation tab | — | **NAV** | |
| Holdings Overlap tab | — | **H** | |
| Export CSV | — | A | |

## 03 Fund Explorer (`03_FundExplorer1/2`) — Phase 2 partial
| Widget | Fields | Status | Notes |
|---|---|---|---|
| Header: name, AMC, category, plan, option, price, change %, AUM | Name, AMC, Category, plan_type, option_type, Price, Change %, Net Assets | A\* | AUM YoY delta ✗ (AUMH). |
| 1Y / 3Y / 5Y return tiles | returns | A | |
| QuantSynthica Score, "Top 5%" | — | **Q** | Snapshot Score prototype possible earlier (Phase 5a). |
| "Regularly Outperforming" badge | cat_pct | A\* | Rule must be documented; do not show until defined. |
| Logo | — | ✗ | Monogram. |
| Overview text (objective, inception, benchmark, manager, expense ratio, min investment, exit load) | Initial Investment | **A: min investment only**; rest **EXP/MGR/new source** | Objective text ✗ (scheme docs). |
| Cumulative returns vs benchmark / rolling returns / calendar returns / trailing table | — | **NAV + BM** | Trailing returns (1M/3M/6M/1Y/3Y/5Y) partially A (3M, 1Y, 3Y, 5Y, YTD). Percentile column from `*_cat_pct` is A; "Rank (out of 421)" derivable A. |
| Risk metrics (vol, Sharpe, Sortino, Calmar, beta, alpha, TE, IR, DD, VaR, CVaR) | — | **NAV + BM + RF** | |
| NAV trend with 50/200 DMA | 50 Day Avg, 200 Day Avg, price | A (summary) / NAV (chart) | Phase 2: show price vs 50/200 and 52-week range bar. |
| 52-week range | 52 Week Low/High, range_position | A | |
| Holdings, sector, country, market-cap allocation, asset allocation | — | **H** | |
| Fund manager card | — | **MGR** | Photo ✗. |
| Sibling share classes | base_fund, n_share_classes | A | Extra feature, not in mockup. |

## 04 Performance Analytics (`04_PerformanceAnalytics1/2`) — Phase 4
Controls: multi-fund select, time period, frequency, benchmark chips.
| Widget | Status |
|---|---|
| KPI strip (5Y return, benchmark return, alpha, Sharpe, Sortino, max DD, outperform periods) | **NAV + BM + RF** |
| Cumulative returns, rolling returns, annual returns, return distribution (violin), consistency bars, risk-return scatter, drawdown comparison, risk-adjusted table | **NAV (+BM)** |
| Monthly returns heatmap, rolling win rate, up vs down market, market cycle table, rolling correlation, period-wise table, top/bottom periods | **NAV (+BM)** |
| Performance attribution (asset allocation, stock selection, currency) | **H + BM** (hard; defer or drop currency effect) |
| Category analysis tab | A (snapshot) / NAV |

## 05 Risk Analytics (`05_RiskAnalytics1/2`) — Phase 4
All widgets (volatility, drawdown, Sortino, VaR/CVaR, Omega, Ulcer, capture ratios, tail risk, stress tests, rolling beta/correlation, skew/kurtosis, volatility regimes) need **NAV + BM + RF**. Stress-test scenarios (COVID, Russia-Ukraine, rate hike) require history covering those windows; schemes launched later show "no data" for that scenario. Efficient frontier line in scatter → Phase 6.

## 06 Quant Research Lab (`06_QuantResearchLab1/2`) — Phase 5
Tabs: Strategy Builder, Backtesting, Factor Analysis, Style Analysis, Alpha & Performance, Risk Models, Optimization, Machine Learning, Strategy Comparison.
| Widget | Status |
|---|---|
| Strategy config (universe, benchmark, rebalance, period) | APP/Q |
| Factor filters (min 3Y CAGR, max expense ratio, min AUM, min Sharpe, max DD) | A for CAGR/AUM; **EXP** for expense; **Q** for Sharpe/DD |
| Scoring method weights | Q |
| Backtest charts (cumulative, rolling, annual, drawdown, win rate, rolling alpha/IR, factor exposure/attribution, best/worst periods) | **NAV + BM + Q**; survivorship-bias label required |
| Style analysis (value/growth/size), factor exposure | **H** or returns-based style regression (NAV) |
| Insights text box | AI/Q (generated from computed stats only) |

## 07 Portfolio Lab (`07_PortfolioLab1/2`) — Phase 6
| Widget | Status |
|---|---|
| Fund picker with search/sort | A (list) |
| Weight sliders, total allocation, save/load/compare portfolios | APP |
| Overview KPIs, cumulative, rolling, drawdown, risk-return scatter, monthly heatmap, vs benchmark table | **NAV + BM** |
| Top holdings combined, sector allocation | **H** |
| Optimisation settings and run, efficient frontier | Q (NAV) |
| Risk contribution, performance attribution, up/down market, historical drawdowns, scenario analysis, Monte Carlo | Q (NAV); scenario results are hypothetical, label clearly |
| Asset class exposure (large/mid/small/international/debt) | A (by Category, approximate) / H |
| Rebalance, import portfolio, export report | APP / Q |

## 08 Fund Comparison (`08_FundComparision1`) — Phase 2 (partial) + Phase 4
| Widget | Status |
|---|---|
| Fund selector (popular, watchlist, custom), up to 5 incl. benchmark | A / APP |
| Key metrics: CAGR 5Y | A (5Y return) |
| Key metrics: Volatility, Sharpe, Sortino, Max DD, Alpha, Beta | **NAV/BM/RF** |
| Key metrics: Expense ratio | **EXP** |
| Cumulative, rolling, annual, drawdown, risk-return scatter | **NAV** |
| Period-wise performance (1Y/3Y/5Y/Since inception) | A (1Y/3Y/5Y); since inception NAV |
| Top holdings / sector allocation comparison | **H** |
| Settings: time period, frequency, benchmark, CAGR vs total return, volatility bands | NAV |
Phase 2 version: side-by-side snapshot comparison only.

## 09 AMC & Fund Manager Intelligence (`09_AMCFundManagerIntelligence`) — Phase 2 partial + Phase 7
| Widget | Status |
|---|---|
| AMC list, scheme counts by tier, scheme count by category | A |
| AUM total, AUM by category | A\* (coverage gaps) |
| AMC inception, website, logo, description | ✗ / **new source** (AMFI AMC list; manual) |
| AUM growth over time | **AUMH** |
| Top performing schemes, category-wise performance, risk-return by category | A (returns) / NAV (risk) |
| Fund manager overview, tenure distribution, "managing since", photos | **MGR** (no source yet) |
| Investment style grid | **H** |

## 10 Market Regime & Allocation (`10_MarketRegime_Allocation`) — Phase 5
All widgets need **NAV/BM for index history (Nifty 500 TRI from 2010)**, India VIX and other indicators (**MACRO**), and model runs (HMM). "Current market regime 72% probability" and "Next 3M outlook" are model outputs; label as research output, not forecast. Gold and international fund universes are small/uncertain in the CSV: check categories before offering them as asset classes.

## 11 AI Research Assistant (`11_AIResearchAssistant`) — Phase 7
| Widget | Status |
|---|---|
| Chat, history, saved research | APP + AI |
| Result tables/charts embedded in answers | Whatever the engine returns; needs NAV/Q for risk and CAGR |
| Data Sources toggles (fund data, holdings, manager, risk, regime, macro, **Web Search**) | Show only sources actually connected; web search is out of scope unless decided |
| "Powered by Gemini 1.5 Pro" | Model selector must reflect the model actually used; confirm provider |
| "SIP Suitable" column, AI insights (suitable for SIP, key risks) | AI/Q; needs explicit rules and disclaimer; avoid personalised advice |
| Export Word/PDF, share | Phase 7 reports |

## 12 Reports & Watchlists (`12_Reports_Watchists`) — Phase 7
| Widget | Status |
|---|---|
| Watchlists, notes, scheduled reports, recent reports, templates | APP (+ background jobs) |
| Watchlist table (AUM, 1Y, 3Y, 5Y, volatility, Sharpe, Max DD) | A for AUM/returns; **NAV** for risk columns |
| Category allocation of watchlist, year-wise returns | A (category) / **NAV** (calendar-year returns) |
| Report templates (comparison, portfolio, SIP, regime, tax planning, custom) | Phase 7; tax planning needs tax rules source |

---

## Availability summary
| Screen | Phase 2 (CSV only) | Needs NAV | Needs other sources |
|---|---|---|---|
| Market Overview | ~65% of widgets | trends, scatter | flows, AUM history |
| Screener | ~70% | risk columns, sparklines, correlation | holdings overlap |
| Explorer | header, snapshot returns, 52w range, trend summary | all charts/risk | holdings, manager, expense, objective |
| Comparison | snapshot table | charts, risk | expense, holdings |
| Performance / Risk / Quant / Portfolio / Regime | ~0% | nearly all | BM, RF, H, MACRO |
| AMC intelligence | counts, performance, AUM | risk | manager, AUM history |
| AI / Reports | app features | metrics | — |

## Widgets proposed to drop or redesign
Net flows and "Top inflow category" (no source); AUM trend lines (no source until AMFI monthly AUM history is built); logos and manager photos; "Web Search" data source; any "vs last month" delta; 1M and 10Y return columns unless NAV history supplies them.

## Sign-off needed
- [ ] Widgets marked to drop are acceptable.
- [ ] Nav decision in `001-navigation.md`.
- [ ] CAGR vs cumulative semantics of the CSV's 3Y/5Y return columns to be verified in Phase 3.


## Update 2026-10-31 (Phase 4)
Now available from NAV: Fund Explorer Performance / NAV Analysis / Risk & Returns / Benchmark tabs, Performance Analytics and Risk Analytics (partial), Screener Sharpe / drawdown / volatility / beta / peer-percentile fields. Benchmark widgets compare with a category average (survivors only), not an index. Still unavailable: holdings, manager, expense ratio, flows, AUM history, GARCH, stress tests.
