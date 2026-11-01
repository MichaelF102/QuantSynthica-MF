# Raw data manifest — Yahoo fund snapshot

| Field | Value |
|---|---|
| File | `yahoo_funds_clean.csv` |
| SHA-256 | `bab0dbed7eb7981afe0ffe3537c4c47ac89220128c722db983d47e7050311271` |
| Size | 2,750,296 bytes |
| Lines | 3,352 (1 header + 3,351 records) |
| Encoding | UTF-8 with BOM (header begins with `﻿Rank`) |
| Columns | 63 |
| Moved to this path | 2026-10-31 (originally `data/yahoo_funds_clean.csv`; earlier name seen: `mf_funds.csv`) |
| Snapshot date | **Unknown.** Must be determined (Phase 3 mapping uses NAV comparison against AMFI). |

Rules: this file is immutable. Never edit in place; derive into bronze/silver/gold. Re-verify with `sha256sum` before each ingestion run and record the hash in `ingestion_runs`.
