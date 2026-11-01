# ADR 005 — Data sources (audit, 2026-10-31)

Status: Proposed. **Licensing is not verified**: technical facts below were tested; usage rights need your confirmation.

## Verified technically
| Source | What | Observed |
|---|---|---|
| Official scheme register, latest NAV file | `https://portal.amfiindia.com/spages/NAVAll.txt` (the `www` host 302-redirects here) | 14,441 scheme records, ~1.5 MB. Plan and option are blank on ~5,700 older records, so they are also parsed from the name. 449 records are dated 1 Nov 2026, later than the system date; flagged, not corrected. |
| Official history report | `…/DownloadNAVHistoryReport_Po.aspx?frmdt=DD-Mon-YYYY&todt=DD-Mon-YYYY[&mf=<amc id>]` | All AMCs in one text file. A 90-day range returned 70 MB / 537k rows in 30 s. A 1-year range returned an HTML error page with HTTP 200, so the client rejects HTML bodies and uses ≤ 90-day windows. Column order differs from the latest-NAV file; parsers read the header. |
| mfapi.in | `https://api.mfapi.in/mf/{code}` full history per scheme (JSON, ~50 KB) | Community-run, no SLA. Observed one truncated JSON body and repeated 60 s read timeouts under 4 parallel requests (≈25 schemes/min). The client validates JSON, retries with backoff, and records failures per scheme. |

## Decision
- Scheme master and identity: the official register (NAVAll). Full-universe official history windows would be ~5 GB for 20 years, so they are reserved for validation and daily increments.
- Bulk per-scheme history: mfapi.in, cached in bronze (raw gz JSON) and silver (Parquet). Spot-check against the official history report before relying on it for results (open item).
- Everything is resumable; failures are stored (`nav_coverage.status = failed`) and retried on the next run.
- Politeness: identifying User-Agent, ≤ 4 workers, small delay between calls.

## Not yet audited / built
Benchmark TRI (NSE Indices), risk-free rate (RBI/FBIL), TER/AUM (AMFI monthly), holdings (AMC disclosures), manager history, IDCW distribution history. Each needs its own licence check before an adapter is written.

## Open licensing questions for the project owner
1. May fetched NAV data be stored and used in a product shown to other people, and is attribution required?
2. Is mfapi.in acceptable as a production dependency, or should the product use only the official files?
3. Any restriction on automated access frequency for the official portal?

Until answered: do not redistribute the raw NAV files or expose bulk NAV downloads.
