# QuantSynthica Mutual Funds

Quant-first research platform for Indian mutual funds. See `docs/plans/` for the phased plan and `docs/decisions/` for ADRs.

## Layout
| Path | Purpose |
|---|---|
| `frontend/` | Next.js (App Router, TypeScript, Tailwind) |
| `backend/` | FastAPI, SQLAlchemy, Alembic, ingestion CLI |
| `data_pipeline/` | Source parsing/validation, pure Python (no DB) |
| `quant_engine/` | Reusable analytics package; must not import web/DB code (tested) |
| `data/raw/yahoo/` | Immutable source CSV (+ `MANIFEST.md` with SHA-256) |
| `docs/` | Plans, ADRs, data dictionary, screen→data map, design tokens |

## Quick start
One command once installed: `npm run install:all` (first time only), then `npm run dev` from the repo root starts the database, the API (8000) and the website (3000).

Step by step:
```bash
python3 -m venv .venv && .venv/bin/pip install -e data_pipeline -e quant_engine -e "backend[dev]"
make up        # postgres (host port 5433) + redis (6380)
make migrate
make ingest    # loads 3,351 funds; re-running the same file is a no-op
make api       # http://localhost:8000/docs
cd frontend && npm install && npm run dev   # http://localhost:3000
make test
```
Host ports 5433/6380 avoid clashing with other local Postgres/Redis; override with `QSMF_PG_PORT`, `QSMF_REDIS_PORT`.

## Data pipeline (Phase 3)
```bash
cd backend
python -m app.cli.pipeline master      # official scheme register (daily NAV file)
python -m app.cli.pipeline recent --days 2200   # NAV history for all schemes from the official history report (90-day windows)
python -m app.cli.pipeline map         # link source funds to official scheme codes; estimates the snapshot date
python -m app.cli.pipeline backfill    # optional: full history per scheme (slow, resumable)
python -m app.cli.pipeline rebuild     # recreate silver NAV store from bronze files (no network)
python -m app.cli.quant                # point-in-time score history, scores, factor research, clusters, regimes (10-12 min)
python -m app.cli.pipeline coverage    # writes data/gold/coverage_report.json (served at /api/v1/data-coverage, page /coverage)
```
Bronze (raw files), silver (Parquet NAV store) and gold (reports) live under `data/` and are git-ignored.
Source notes and open licensing questions: `docs/decisions/005-data-sources.md`.

## UI
`DESIGN.md` is the design system and governs all frontend work.

## Status
Phases 1 to 7 built locally (not deployed; see `docs/plans/phase7-progress.md` for the readiness report and `docs/deployment.md`). See `docs/plans/phase5-progress.md` for the Phase 5 findings (the composite score shows no net-of-cost selection advantage) and `docs/plans/phase6-progress.md` for portfolio tools (builder, optimisation, SIP/SWP, rebalancing, stress testing).
