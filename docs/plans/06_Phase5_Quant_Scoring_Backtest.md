# Phase 5 — Quant Engine Part 2: Scoring, Research, Backtesting (Weeks 8–10)

## 5a. Snapshot prototype score (superseded: build from NAV instead)
**Finding (2026-10-31, see Data Coverage page):** the source's 1Y/3Y/5Y returns, and therefore the `1year/3year/5year_return_cat_pct` and `_z` columns, are measured to earlier, fund-specific dates and are not aligned to the snapshot. YTD and 3M are current. A prototype built on the stale columns would rank on inconsistent dates, so compute returns from NAV (now available for ~2,580 accepted schemes) instead.

Original note:
Built from CSV percentile/z columns only: `1year/3year/5year_return_cat_pct`, `range_position_cat_pct`, `trend_50_200_cat_pct`, `log_net_assets_cat_pct`. Label it **"Snapshot Score (prototype)"**, distinct from the full QuantSynthica Score. No risk-adjusted or downside factor possible yet.

## 5b. QuantSynthica Fund Score v1 (needs NAV)
Factors and initial weights (hypotheses, not validated): Performance 25, Risk-adjusted 25, Consistency 20, Downside 15, Momentum 10, Stability 5.
- Peer groups: Equity / Debt / Hybrid / Other, then category. Never rank liquid vs small-cap together.
- Per metric: raw → winsorise → category percentile or z → direction-aware → factor score → weighted composite.
- Missing factors: coverage-aware renormalisation + completeness indicator; never zero-fill; minimum-coverage threshold to be scored.
- Store per `methodology_version`; changes to weights/formulas create a new version.
- Stability factor needs AUM/expense/manager history; drop or reweight until available (document the reweighting as a version).

## 5c. Research modules
- Factor research: IC/rank-IC of each factor vs forward returns, quantile spreads, decay.
- Statistical analysis: distributions, correlations, regressions.
- Clustering (category-aware or within tier): K-Means, hierarchical, DBSCAN, PCA, GMM; silhouette, sizes, centroid interpretation; labels derived from measured traits.
- Regimes: volatility-, trend-based, HMM/GMM/Markov switching, using only info available at each date.

## 5d. Backtesting engine
Strategies: momentum, risk-adjusted momentum, consistency, low-vol, quality, multi-factor, regime-aware.
Required controls: point-in-time universe (funds that existed then, including since-closed ones), min history, rebalance frequency, lookback, transaction cost, exit loads, switching delay (redemption + purchase settlement), tax toggle, benchmark, out-of-sample split (walk-forward). Jobs run via worker + job IDs, results stored with config hash for reproducibility.
**Survivorship caveat:** the CSV and current AMFI list only contain living schemes. Historical universe needs merged/closed scheme data from AMFI history; until then label backtests as "survivor-biased" in the UI.

## Gate
Scores reproducible from stored inputs; factor tests show whether scores predict out-of-sample (report honestly if they don't); backtests free of look-ahead; no claim of profitability from a single sample.


## Status (2026-11-01)
Built and verified; see `docs/plans/phase5-progress.md` for results, corrections, and what is not done.

Gate check:
- Every factor has a documented formula (`/quant/methodology`, Fund Scoring page) ✔
- Category-relative scoring and visible missing-factor coverage ✔
- Historical scores point-in-time (tested) ✔
- Out-of-sample evaluation available (in-sample vs out-of-sample split on every backtest) ✔
- Backtests reproducible (config hash, identical rerun) ✔
- Score reproducible from stored inputs ✔
- Persistence / predictive test: **done, and the result is weak**: momentum shows a modest, significant link; the composite does not beat equal-weight after costs ✔ (reported honestly)
