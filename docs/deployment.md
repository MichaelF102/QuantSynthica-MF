# Deployment on free plans: Vercel (frontend) + Render free (API) + free external Postgres

**Status: configuration written and tested locally; never applied to real accounts.** Everything below the line "What was measured" was run on this machine; the Render, Vercel, Neon and GitHub Actions steps were not.

## Why the free plans needed changes
Render's free web service has **512 MB RAM, no persistent disk, no cron jobs**, sleeps after 15 minutes idle, and its free Postgres is **deleted after 30 days**. The first version of this project would have used about 1.2 GB for a portfolio request. It now fits:

| What was measured (this machine, real data, 21.8 M NAV rows) | Before | After |
|---|---|---|
| Memory after start-up | 235 MB | 154 MB |
| Single fund analytics request | 586 MB peak, 9.5 s | about 210 MB peak, 0.3 s |
| Portfolio analysis of 6 funds | 1,161 MB peak | about 215 MB peak, 0.3 s |
| 15 concurrent heavy requests | not tried | **325 MB peak** (limit 512 MB) |

What changed: (1) portfolio tools load only the funds you pick, not the whole universe; (2) the risk-free series, category benchmarks and equity-market proxy are precomputed into small files (benchmarks as per-category return sums and counts, so a fund's benchmark no longer needs its peers' NAV histories; a test proves the result matches the direct calculation); (3) NAV reads prune Parquet row groups instead of decompressing whole years; (4) scikit-learn and scipy are loaded only when something needs them (Ledoit-Wolf and the skewness/kurtosis/normal-quantile functions are now written in numpy/stdlib and tested against the library versions); (5) `ARROW_DEFAULT_MEMORY_POOL=system` and `MALLOC_*` settings, which alone halved the peak because Arrow's default allocator never returned memory; (6) running **new backtests is switched off** on the hosted API (`QSMF_ENABLE_BACKTESTS=false`) because they need about 1 GB; stored results are still served.

Remaining headroom is roughly 180 MB on the busiest tested mix. A Render free instance also has a small share of a CPU, so expect slower responses than measured here, and 30 to 60 seconds for the first request after the service has slept.

## Architecture
| Piece | Where | Notes |
|---|---|---|
| Frontend | Vercel (Hobby, free) | Root directory `frontend`. Builds without the API reachable (verified). |
| API | Render free web service (`render.yaml`) | Python runtime, no Docker. |
| Postgres | **Neon** or **Supabase** free tier | Not Render's free database (expires). About 30 MB of data today. |
| NAV data | GitHub Release asset `data-latest` (142 MB) | Downloaded into the build by `scripts/fetch_data.sh`. Read-only at run time. |
| Daily refresh | GitHub Actions `refresh-data.yml` (free minutes) | Replaces Render cron + disk. Rebuilds data, uploads the bundle, triggers a Render redeploy. |

Redis is not used. The `/api/v1/admin/refresh` endpoint (for a paid Render disk setup) stays off unless `QSMF_ADMIN_TOKEN` is set; do not use it on the free plan.

## Environment variables
| Variable | Where | Value |
|---|---|---|
| `QSMF_ENVIRONMENT=production` | Render | Start-up fails if the DB URL has the dev password or CORS lists localhost. |
| `QSMF_DATABASE_URL` | Render, GitHub secret | Neon/Supabase connection string. `postgres://` and `postgresql://` are converted automatically. |
| `QSMF_CORS_ORIGINS` | Render | JSON list with your Vercel URL(s), e.g. `["https://your-app.vercel.app"]`. |
| `QSMF_DATA_URL` | Render | `https://github.com/OWNER/REPO/releases/download/data-latest/qsmf-data.tar.gz` |
| `QSMF_DATA_SHA256_URL` | Render | Same URL plus `.sha256` (optional; a mismatch fails the build). |
| `QSMF_GITHUB_TOKEN` | Render | Only for a private repo. **Untested**: if the download fails, make the repo public or host the bundle elsewhere (Cloudflare R2 and Backblaze B2 have free tiers). |
| `QSMF_ENABLE_BACKTESTS=false`, `ARROW_DEFAULT_MEMORY_POOL=system`, `MALLOC_ARENA_MAX=2`, `MALLOC_TRIM_THRESHOLD_=131072` | Render | Already in `render.yaml`. Keep them. |
| `QSMF_ANTHROPIC_API_KEY` | Render | Optional (assistant paragraph). Never in Vercel. |
| `NEXT_PUBLIC_API_URL` | Vercel | The Render URL. |
| `RENDER_DEPLOY_HOOK_URL` | GitHub secret | Render service > Settings > Deploy Hook. |

## Steps (first time)
1. Push the repo to GitHub (nothing is committed yet). Public is simplest.
2. Create a free Neon (or Supabase) database. Run migrations and copy the reference data from your local database:
   ```bash
   cd backend && QSMF_DATABASE_URL=<neon url> ../.venv/bin/alembic upgrade head
   SRC=postgresql://qsmf:qsmf@localhost:5433/qsmf DST=<neon url, plain postgresql://> scripts/seed_remote_db.sh
   ```
   The script copies every reference and analytics table (not users or saved items) and checks row counts. Rehearsed here against a scratch local database; needs `pg_dump` and `psql` installed.
3. Publish the data bundle: `gh auth login` then `scripts/publish_data.sh` (creates release `data-latest`).
4. Render: **New > Blueprint** from the repo; fill the prompted variables. Check `https://<service>.onrender.com/api/v1/health`.
5. Vercel: import the repo, Root Directory `frontend`, set `NEXT_PUBLIC_API_URL`. Then put the Vercel URL into `QSMF_CORS_ORIGINS` on Render.
6. GitHub: add secrets `QSMF_DATABASE_URL` and `RENDER_DEPLOY_HOOK_URL`; run the `refresh-data` workflow once by hand and read its log.

## Known limits of the free setup
- **Cold starts.** The API sleeps when idle; the first request waits while it starts. A free uptime pinger avoids this but uses your 750 free hours.
- **The refresh pipeline has never run against a hosted database or on GitHub's runners.** Treat the first runs as testing. A failed workflow run leaves the old data in place (the bundle is only uploaded at the end).
- **New backtests are unavailable online** (stored results work). Run them locally.
- **Sessions and saved items** live in the hosted Postgres; free tiers have connection and storage limits and Neon pauses when idle (the first query after a pause is slow).
- **Data licensing** questions (ADR 005) are still open; publishing a public GitHub release makes the NAV bundle public.
- **Security**: passwords use scrypt; sessions are opaque tokens (SHA-256 stored, 14 days) kept in browser `localStorage`, which any injected script can read; moving to an `HttpOnly` cookie is advisable and easier once the site and API share a registrable domain. Login throttling is per process. No email verification, password reset or OAuth.
- Never run the browser tests against the hosted API: they create accounts.

## CI (`.github/workflows/ci.yml`)
Lint (errors only), quant-engine tests, data-integrity tests, migration upgrade/downgrade/upgrade, API tests, frontend type-check/lint/build. Never run on GitHub. No Playwright or OpenAPI-contract check in CI.

## Backups
Neon/Supabase keep short point-in-time history on the free plan; `scripts/backup_db.sh` makes a portable dump. The NAV store can be rebuilt from public sources and every refresh publishes a new bundle (older bundles are overwritten, so keep a copy if you want history). **No restore has been rehearsed.**
