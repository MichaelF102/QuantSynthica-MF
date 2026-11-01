# Phase 3 — Historical Data Pipeline (Weeks 3–6)

## Step 0 — Source & licensing audit (first, 1–2 days)
For each source record in `docs/decisions/005-data-sources.md`: URL, auth, rate limits, history depth, terms of use/redistribution, automated-access policy. Build adapters only for sources cleared.
Candidates: AMFI (NAVAll + history report), mfapi.in, NSE Indices, RBI/FBIL, AMFI TER/AUM, AMC disclosures.

## Step 1 — AMFI scheme master
- Adapter fetches `https://portal.amfiindia.com/spages/NAVAll.txt` (follow redirects; the `www` URL 302s). Parse semicolon format: code; ISIN payout/growth; ISIN reinvestment; name; plan; option; NAV; date. Section headers give category and AMC.
- Bronze: raw file with timestamp. Silver: `amfi_schemes` (code, ISINs, name, plan, option, AMC, category, latest NAV, NAV date).
- Verified 2026-10-31: 14,441 schemes, NAV date 30-Oct-2026.

## Step 2 — Yahoo → AMFI mapping (the key risk)
Experiment result (see 00_README): 1,017 unique confirmed, 1,648 ambiguous many-to-one, 415 probable/name-only, 271 unmapped (mostly insurer funds). The prototype is too loose. Production matcher:
1. Normalise names (abbreviations: Gr, Reg, Dir, Cnsv, Hyb, Mn, IDCW/Dividend, Pru, etc.) in a versioned dictionary.
2. Restrict by AMC (AMC map table, reviewed manually for the 55 AMCs).
3. Hard constraints: plan and option must agree when specified; IDCW frequency/payout vs reinvestment must agree.
4. Score = name similarity + NAV closeness (value and date). Tolerance configurable; record the CSV snapshot date question (CSV price date is unknown — determine it, otherwise NAV comparison is only approximate).
5. Enforce one-to-one assignment (Hungarian/greedy with tie-break); conflicts go to a review queue.
6. Output `scheme_mapping` with status (`confirmed`, `probable`, `ambiguous`, `unmapped`, `not_amfi_scheme`), score, method, matcher version. Never drop unmapped funds.
7. Manual override file `data/reference/mapping_overrides.csv`, version-controlled.
8. Report: coverage by tier/category/AMC; one-to-one rate is the headline number.

## Step 3 — NAV history
- Primary: AMFI history report in date-range chunks (loop + stitch), per scheme or per AMC. Convenience/fallback: mfapi.in `/mf/{code}` with caching, retries, backoff (one call timed out in testing).
- Bronze raw responses; Silver `nav_history(scheme_id, date, nav, source, ingested_at)` partitioned Parquet by year/AMC; unique (scheme, date, source).
- Idempotent upserts; incremental daily job (cron/scheduled Python, no Airflow yet); backfill CLI with resume.
- Quarantine invalid rows (≤0, non-numeric, future dates).

## Step 4 — Benchmarks and risk-free
- Benchmark TRI (Nifty 50/500, etc.) from NSE Indices after licence check; price index (yfinance `^NSEI`) is NOT TRI — label accordingly.
- Benchmark mapping table (category → default benchmark) documented as an assumption.
- Risk-free: RBI/FBIL T-bill/G-Sec series; record the convention used.

## Step 5 — Later (separate tickets)
AMFI TER/AUM monthly; AMC holdings parsers (one per AMC, own tests); manager history; IDCW distribution history.

## Data quality checks (framework)
Duplicate dates, gaps (business-day calendar), jump detection (e.g. |daily change| > threshold) → flag, do not delete; stale NAV; plan/option consistency; category mapping sanity. Results to `data_quality_issues`; summary report per run.

## Total-return rule
Growth series: NAV-based. IDCW series: needs distribution history to build total return; until available, mark IDCW total-return as unavailable. Never mix Direct/Regular or Growth/IDCW histories.

## Tables
`ingestion_runs`, `scheme_mapping`, `nav_history` (Parquet + metadata in PG), `benchmarks`, `benchmark_history`, `risk_free_rates`, `data_quality_issues`.

## Tests
Parser fixtures from real AMFI lines; matcher golden set (hand-labelled ~200 funds incl. IDCW variants); idempotent rerun; Parquet partition integrity.

## Gate
NAV history loaded for all confirmed schemes; rerun produces zero duplicates; mapping coverage report published with one-to-one rate; licensing decisions recorded.

## Status (2026-10-31)
**Built and verified on real data**
- Official register: 14,441 schemes. NAV store (Parquet, 11.8M observations, ~6 years for all schemes via the official history report; up to 20 years for 313 schemes via mfapi.in). Bronze raw files kept; `rebuild` recreates silver from bronze without network.
- Idempotency: re-loading the last 120 days inserted 0 / updated 0 / unchanged 731,373. Cross-process write lock after a real corruption bug (two loaders sharing one temp file).
- Matcher v1.0: 3,046 non-insurer schemes: 2,094 confirmed (68.8%), 481 probable, 7 name-only, 66 ambiguous, 432 unmapped incl. 271 insurer funds labelled "not a registered scheme". Slot conflicts: 0 (also enforced by a partial unique index).
- Snapshot date estimated as **2026-10-30** (565 of 584 high-confidence funds equal the official NAV to the cent).
- Direct-Growth families: 438 of 484 mapped, all 438 with ≥3 years of NAV.
- Quality scan: 24 invalid NAVs, 27 gaps, 109 large moves flagged (none deleted). Source agreement: 244 of 446,917 overlapping observations differ between the two sources (0.055%); official wins.
- Source return fields: YTD and 3M are current; 1Y/3Y/5Y are annualised but measured to earlier, fund-specific dates.

**Gate check:** NAV history loaded for matched schemes ✔ · rerun creates no duplicates ✔ · mapping coverage report ✔ · licensing decisions recorded ✘ (open questions in ADR 005).

**Not done:** benchmark TRI, risk-free rate, IDCW distribution history (IDCW total return stays unavailable), closed/merged schemes (survivorship), daily incremental job, resolving the 66 ambiguous and 432 unmapped rows (manual overrides file is ready: `data/reference/mapping_overrides.csv`), mfapi.in full history for schemes beyond the first ~280 (the official report already gives 6 years).
