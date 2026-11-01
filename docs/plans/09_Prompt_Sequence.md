# Antigravity Prompt Sequence

| Prompt | Phase(s) | Run when | Adjustments to the original prompt |
|---|---|---|---|
| 1. Master initialization | 0–1 | First | Use `data/raw/yahoo/yahoo_funds_clean.csv`; add instructions for BOM, quarantine flags, `base_fund` grouping, external-ID model. |
| 4a. Frontend: Discover pages | 2 | After Prompt 1 | Split from original Prompt 4; only Overview, Screener, Explorer, Comparison; gated states for missing data. |
| 2. Data engineering | 3 | After Phase 1 (parallel with 4a) | Replace "AMFI codes wherever available" with the matcher spec in `04_Phase3_Data_Pipeline.md` including one-to-one rule and mapping statuses; AMFI URL is `portal.amfiindia.com`. |
| 3. Quant engine | 4–5 | Part 1 anytime on synthetic data; Part 2 after NAV exists | Split into 3a (performance/risk) and 3b (scoring, clustering, regimes, backtests). |
| 4b. Frontend: analytics and quant pages | 4–5 | After 3a/3b | Remaining pages from original Prompt 4. |
| 5. Portfolio, AI, integration | 6–7 | Last | As written, plus survivor-bias labelling on backtests. |

After each prompt: inspect output, run tests/build, commit (conventional commits).
