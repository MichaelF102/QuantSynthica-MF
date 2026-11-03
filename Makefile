PY=.venv/bin/python
.PHONY: up down migrate ingest test e2e api lint deploy-db deploy-data
up:        ## start postgres + redis (host ports 5433/6380)
	docker compose up -d postgres redis
down:
	docker compose down
migrate:
	cd backend && ../$(PY) -m alembic upgrade head
ingest:
	cd backend && ../$(PY) -m app.cli.ingest
api:
	cd backend && ../$(PY) -m uvicorn app.main:app --reload --port 8000
test:      ## run each package's tests from its own directory (avoids folder/package name shadowing)
	cd data_pipeline && ../$(PY) -m pytest -q
	cd quant_engine && ../$(PY) -m pytest -q
	cd backend && ../$(PY) -m pytest -q
lint:
	.venv/bin/ruff check backend data_pipeline quant_engine
e2e:       ## browser tests; needs API on :8000 and `npm run build && npm run start` on :3000
	cd frontend && npx playwright test

deploy-db:    ## first-time hosted database: make deploy-db DST=postgresql://user:pass@host/db  (needs pg_dump and psql; local DB running)
	@test -n "$(DST)" || { echo "usage: make deploy-db DST=<neon/supabase url>"; exit 1; }
	cd backend && QSMF_DATABASE_URL="$(DST)" ../$(PY) -m alembic upgrade head
	SRC=postgresql://qsmf:qsmf@localhost:5433/qsmf DST="$(DST)" scripts/seed_remote_db.sh
deploy-data:  ## publish the NAV data bundle to the GitHub release Render downloads at build time (needs `gh auth login`)
	scripts/publish_data.sh
