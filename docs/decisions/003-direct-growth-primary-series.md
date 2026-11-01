# ADR 003 — Direct-Growth as the primary analytic series

Status: Proposed

## Context
Rankings and scores that include every share class double-count the same portfolio, and IDCW series need distribution history for total return.

## Decision
- Default ranking/scoring universe: **Direct plan + Growth option** share class of each fund family (one entry per family). If a family has no Direct-Growth class, fall back to Regular-Growth and flag it.
- Other classes are shown as variants on the fund page and are available in the screener via toggle.
- IDCW classes: total return unavailable until distribution history exists. They are excluded from risk/score calculations and display "not available".
- Never mix Direct/Regular or Growth/IDCW histories.

## Consequences
Score and ranking counts will be much lower than 3,351; communicate "N fund families" separately from "N share classes". Check the share of families with a usable Direct-Growth class during Phase 1 reporting.

## Measured impact (2026-10-31)
Only **484 of 1,196** fund families (40%) have a Direct+Growth share class in the CSV (see `docs/data_dictionary/data_quality_report.md`). The fallback chain (Regular+Growth, then flagged) therefore matters, and plan 'Unspecified' (975 rows) will cause some families to have no confirmed Direct class. Decide the fallback rule before Phase 5 scoring.
