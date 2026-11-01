PY=.venv/bin/python
.PHONY: up down migrate ingest test e2e api lint
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
