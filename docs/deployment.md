# Deployment on free plans: Vercel (frontend) + Render free (API) + a free Postgres

## Quick start (about 15 minutes, four free accounts, no paid features)
You need free accounts on **GitHub**, **Neon** (or Supabase), **Render** and **Vercel**. Four steps, three of them are clicks.

1. **Put the repo on GitHub** (public is simplest) and publish the data once:
   ```bash
   gh auth login
   make deploy-data                  # uploads the 142 MB NAV bundle as release "data-latest"
   ```
2. **Create a free Neon database**, copy its connection string, then fill it:
   ```bash
   make deploy-db DST='postgresql://user:pass@ep-xxxx.neon.tech/neondb?sslmode=require'
   ```
   (needs `pg_dump` and `psql`, and your local database running; takes a minute.)
3. **Render: New > Blueprint**, pick the repo. It asks for exactly one value: `QSMF_DATABASE_URL` (the Neon string). Everything else, including where to download the data and which websites may call the API, is already in `render.yaml`. When it is live, open `https://<service>.onrender.com/api/v1/health`.
4. **Vercel: Add New > Project**, pick the repo, set **Root Directory** to `frontend`, add one environment variable `NEXT_PUBLIC_API_URL` = your Render URL, deploy. No CORS step: the API already accepts any `https://*.vercel.app` site.

Optional, both recommended:
- **Stop the cold starts.** In GitHub: Settings > Secrets and variables > Actions > Variables, add `API_URL` = your Render URL. The `keepalive` workflow then pings it every 10 minutes (one always-on free service fits inside Render's 750 free hours).
- **Daily data refresh.** Add secrets `QSMF_DATABASE_URL` and `RENDER_DEPLOY_HOOK_URL` (Render service > Settings > Deploy Hook) and the `refresh-data` workflow keeps the NAVs current. Skip it and the site simply shows the data you published in step 1.

Private repo, custom domain or another data host? See "Environment variables" below.

---

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
| `QSMF_CORS_ORIGINS`, `QSMF_CORS_ORIGIN_REGEX` | Render | Already set in `render.yaml` (`[]` and any `https://*.vercel.app`). Only add your own domain to `QSMF_CORS_ORIGINS` as a JSON list, e.g. `["https://funds.example.com"]`. |
| `QSMF_DATA_URL` | Render | Optional. Worked out from the repository by default; set it only to download from somewhere else. |
| `QSMF_DATA_SHA256_URL` | Render | Optional. The `.sha256` next to the bundle is used automatically; a mismatch fails the build. |
| `QSMF_GITHUB_TOKEN` | Render | Only for a private repo. **Untested**: if the download fails, make the repo public or host the bundle elsewhere (Cloudflare R2 and Backblaze B2 have free tiers). |
| `QSMF_ENABLE_BACKTESTS=false`, `ARROW_DEFAULT_MEMORY_POOL=system`, `MALLOC_ARENA_MAX=2`, `MALLOC_TRIM_THRESHOLD_=131072` | Render | Already in `render.yaml`. Keep them. |
| `QSMF_ANTHROPIC_API_KEY` | Render | Optional (assistant paragraph). Never in Vercel. |
| `NEXT_PUBLIC_API_URL` | Vercel | The Render URL. |
| `RENDER_DEPLOY_HOOK_URL` | GitHub secret | Render service > Settings > Deploy Hook. |

## Steps
See the quick start at the top. The `make deploy-db` target runs `alembic upgrade head` on the hosted database and then `scripts/seed_remote_db.sh`, which copies every reference and analytics table (not users or saved items) and checks row counts (rehearsed against a scratch local database).

## Known limits of the free setup
- **Cold starts.** The API sleeps after 15 idle minutes and takes 30 to 60 s to wake. The optional `keepalive` workflow (a GitHub Actions ping every 10 minutes) avoids this and fits inside the 750 free hours for one service. The landing page shows dashes instead of waiting more than 8 s for its statistics.
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
