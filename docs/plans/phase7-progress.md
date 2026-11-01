# Phase 7 progress and readiness report

Status as of 2026-11-01: **built and verified locally. Not deployed.** Target is Vercel (frontend) + Render **free** (API) + a free external Postgres (Neon/Supabase), data refreshed by GitHub Actions. The configuration (`render.yaml`, `frontend/vercel.json`, `docs/deployment.md`) was written but never applied to real accounts.

## Verification
- Tests: data pipeline 47, quant engine 112, backend 105 (+1 skipped), browser 65 (all Phase 2 to 7 specs plus design checks at 375/1280/1920 px). `tsc` and `eslint` clean; error-level `ruff` clean (the CI lint gate).
- Migrations 0001 to 0005 upgrade, downgrade to base and upgrade again on a scratch database.
- Assistant evaluation on real data: every figure in four sample answers is traceable to a sourced fact (checked by the number validator).
- Backend Docker image build: not verified (see below).

## What was built
| Area | Delivered |
|---|---|
| AMC intelligence | `/amc`, `/amc/[id]`, `/api/v1/amcs`. Direct Growth plans only; each fund is a percentile among its own category peers; an AMC is the **median** fund percentile, ranked only with at least 5 scored funds in 3 categories (26 of 33 AMCs qualify). Also shares above median / top / bottom quartile and category concentration. |
| Reports | PDF and Excel for fund, portfolio and AMC (`POST /api/v1/reports/{kind}.{pdf,xlsx}`), buttons on the fund, Portfolio Builder and AMC pages. Reports are built from the same service functions as the dashboards; tests compare Excel cells with the API numbers (to 12 significant digits). |
| Accounts | Email and password (scrypt), opaque bearer sessions (SHA-256 stored, 14 days), login throttling, `/account` page, per-user saved items (watchlist, portfolio, screen, alert, research) with ownership enforced in every query and tested across two users. Watch button on fund pages; Portfolio Builder saves to the account when signed in. |
| AI Research Assistant | `/assistant`, `POST /api/v1/assistant/ask` (sign-in required, calls logged without answer text). Tools over the existing services: fund performance, risk, score explanation, AMC ranking, fund lookup. Answers are composed from **facts** (value, unit, as-of date, source); unavailable data is listed, never filled. Refuses advice and predictions, refuses instruction-override attempts, does not guess an unknown fund, sanitises text before it can reach a model. |
| Deployment | `render.yaml` (free plan, no disk), `frontend/vercel.json`, data bundle scripts (`publish_data.sh`, `fetch_data.sh`, `seed_remote_db.sh`), `refresh-data.yml` GitHub Actions workflow, a memory-lean API (peak 325 MB under 15 concurrent heavy requests, was 1.2 GB), token-protected `/api/v1/admin/refresh` (off by default, for paid disks), hosted-Postgres URL normalisation, production start-up guard against development credentials, GitHub Actions CI, optional Dockerfiles, `scripts/backup_db.sh`, `docs/deployment.md`. |

## Known limitations (read before relying on this)
1. **The assistant's language-model layer has never been run against a real model.** No API key was available. Without `QSMF_ANTHROPIC_API_KEY` the assistant works from tools only. With a key, the model sees only structured facts, and its paragraph is discarded unless every number matches a fact and it contains no advice; that validator and the fallback paths are unit-tested with a fake model, but the live API call is untested.
2. **Routing is keyword and name matching, not understanding.** The assistant answers returns, risk, score and AMC questions for funds named in full; other questions get "could not match", by design. Portfolio analysis and comparison are not wired into the assistant yet (the plan listed them).
3. **No OAuth, email verification or password reset.** Sessions live in `localStorage` (exposed to any script injection; an `HttpOnly` cookie is the recommended hardening). Login throttling is per process.
4. **Not built from the plan:** report storage (reports are generated on demand), alerts and saved screens (the storage exists, there is no UI or evaluation job), research history, manager pages (no manager data exists), an OpenAPI contract-diff check in CI, Playwright in CI.
5. **AMC rankings inherit the score's weakness.** Backtests showed the composite score has no net-of-cost selection edge; the AMC page says so. Survivors only (closed or merged schemes are absent), and only funds with NAV links and 3 years of history are scored.
6. **Data caveats unchanged:** survivorship bias, mapping coverage (only Growth schemes with confirmed AMFI links are analysable; IDCW NAVs exclude payouts), proxy risk-free rate and category-average benchmark, source licensing questions still open (ADR 005).
7. **Test hygiene:** the browser tests create `@example.com` accounts in whatever database the API uses. Run them against a disposable database; 36 such accounts created during development were removed from the dev database.

## Not verified
- Anything on Render or Vercel (the blueprint, the build-time data download, the GitHub Actions refresh against a hosted database, memory under Render's real CPU and cgroup limits). CI has never run on GitHub.
- Backup restore has not been rehearsed.
- Backend image build: **not verified.** Two attempts (the second with a 120 s pip timeout and 5 retries) both failed on PyPI read timeouts from this machine. The Dockerfile has never produced an image; retry on a stable network.

## Test-isolation bug found and fixed
A new test module imported the app at collection time, which bound the API to the **development** database before the test database was selected; the suite then ran against dev data. Nothing in dev was changed (row counts verified), but `tests/conftest.py` now rebinds settings and the engine to the throwaway database so import order cannot cause this again.

## How to run
```bash
make up && make test
cd backend && ../.venv/bin/alembic upgrade head && ../.venv/bin/python -m uvicorn app.main:app --port 8000
cd ../frontend && npm run build && npm run start -- -p 3000 && npx playwright test
```
