# QuantSynthica Mutual Funds — Implementation Plan (Index)

Quant-first Indian mutual fund research platform. Scope: full. Data: CSV + historical NAV pipeline in parallel. Frontend: Next.js + FastAPI.

## Phase files
| File | Phase | Weeks |
|---|---|---|
| `01_Phase0_Prep.md` | Prep | 2–3 days |
| `02_Phase1_Foundation.md` | Foundation + CSV ingestion | 1–2 |
| `03_Phase2_Discover_Pages.md` | Market Overview, Screener, Explorer, Comparison | 3–5 |
| `04_Phase3_Data_Pipeline.md` | AMFI/NAV/benchmark/risk-free pipeline | 3–6 (parallel with Phase 2) |
| `05_Phase4_Quant_Performance_Risk.md` | quant_engine part 1 | 6–8 |
| `06_Phase5_Quant_Scoring_Backtest.md` | quant_engine part 2 | 8–10 |
| `07_Phase6_Portfolio.md` | Portfolio management | 10–12 |
| `08_Phase7_Intelligence_Deploy.md` | AMC, AI, reports, deploy | 12–14 |
| `09_Prompt_Sequence.md` | Which Antigravity prompt runs when | — |

## Ground rules (apply to every phase)
1. One calculation engine (`quant_engine`), no duplicated metric logic.
2. Point-in-time research; no look-ahead or survivorship bias.
3. Canonical identity: scheme, plan, option are separate. Yahoo symbol is an external ID only.
4. Lineage: every metric traceable to source, date, methodology version.
5. No fabricated data. Missing stays missing and the UI shows "data not available".
6. Scores are research indicators, not predictions, until validated out-of-sample.
7. Versioned methodology for any formula or weight change.

## Verified facts about the starting data
- File: `data/yahoo_funds_clean.csv` — 3,351 rows, 63 columns, unique `Symbol`, 55 AMCs, 49 categories.
- Tiers: Debt 1,328 / Equity 1,276 / Hybrid 577 / Other 170.
- Plan: Direct 1,557, Unspecified 975, Regular 808, Institutional 11. Option: IDCW 1,910, Growth 1,026, Unspecified 415.
- Net Assets missing for 1,067 rows (32%); Net Assets repeats across share classes of one scheme, so aggregate by `base_fund` before summing.
- `split` is a train/test label (2,739 / 612): never a production feature.
- Single snapshot date: no history, so no historical scoring or backtests from the CSV alone.
- UI mockups in `ui/` (19 PNGs, 12 screens) contain US placeholder data and widgets the CSV cannot feed (net flows, AUM trend, holdings, expense ratio, Sharpe/drawdown).

## Chosen data sources
| Need | Source | Status |
|---|---|---|
| Scheme master + latest NAV | AMFI `https://portal.amfiindia.com/spages/NAVAll.txt` (old `www` URL 302-redirects) | Verified reachable; 14,441 schemes, dated 30-Oct-2026 |
| NAV history | AMFI history report (date-range chunks); mfapi.in as cache-backed convenience | mfapi.in list endpoint works; per-scheme call timed out once — add retries, do not rely on it alone |
| Benchmark TRI | NSE Indices downloads | Licensing to verify |
| Risk-free | RBI DBIE / FBIL | To build |
| TER, AUM | AMFI monthly data | Later |
| Holdings | AMC monthly disclosures | Later, per-AMC parsers |
| yfinance | Metadata/sanity checks only | Already the CSV source |

## Mapping experiment result (Yahoo CSV → AMFI), run 2026-10-31
Name-normalisation + AMC restriction + NAV confirmation (±0.5%):
| Status | Funds |
|---|---|
| Confirmed, unique AMFI target | 1,017 |
| Confirmed NAV but several CSV rows hit one AMFI code (matcher too loose; IDCW sub-options collapse) | 1,648 |
| Probable (NAV within 3%) | 120 |
| Name match only, NAV mismatch (likely stale/different date) | 295 |
| Unmapped | 271 |

Insurer/ULIP funds (305 per CSV) mostly do not exist in AMFI: expected and should be labelled "not an AMFI scheme". The 1,648 group is **not** a success: it must be resolved in Phase 3 (use ISIN, plan, option, IDCW frequency, and exact NAV+date tie-breaks; enforce one-to-one assignment). Do not report coverage until the one-to-one rate is measured.
Scratch outputs: `/tmp/claude-1000/-home-michaelfernandes-Desktop-Projects-QuantSynthica-Mutual-Funds/57520251-7f9e-4816-969e-ec2f67fc971d/scratchpad/match_results.json`, script in `.../scratchpad/scripts/match.py` (temporary; Phase 3 reimplements properly in `data_pipeline/`).

## Target nav (final)
DISCOVER: Market Overview, Fund Screener, Fund Explorer, Fund Comparison
ANALYTICS: Performance, Risk, AMC Intelligence
QUANT RESEARCH: Scoring, Factor Research, Statistical Analysis, Clustering, Regime, Backtesting
PORTFOLIO: Builder, Analytics, Optimization, SIP/SWP, Rebalancing, Stress Testing
INTELLIGENCE: AI Research, Reports, Watchlists & Alerts
(Phase 0 must reconcile this with the mockup top-bar labels.)
