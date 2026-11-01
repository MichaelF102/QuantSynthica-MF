"""DB-backed tests run against a throwaway database on the dev Postgres.

Requires the compose postgres to be up. Skipped automatically if unreachable.
"""
import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ADMIN_URL = os.environ.get("QSMF_TEST_ADMIN_URL", "postgresql+psycopg://qsmf:qsmf@localhost:5433/postgres")
TEST_DB = "qsmf_test"
REAL_CSV = Path(__file__).resolve().parents[2] / "data" / "raw" / "yahoo" / "yahoo_funds_clean.csv"


@pytest.fixture(scope="session")
def test_db_url():
    admin = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as c:
            c.execute(text(f"drop database if exists {TEST_DB} with (force)"))
            c.execute(text(f"create database {TEST_DB}"))
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"postgres not reachable: {exc}")
    url = make_url(ADMIN_URL).set(database=TEST_DB).render_as_string(hide_password=False)
    os.environ["QSMF_DATABASE_URL"] = url
    # Anything that imported the app earlier may have cached settings and an engine for the DEVELOPMENT database. Rebind both,
    # so tests can never write to it regardless of import order.
    import app.db as appdb
    from app.core.config import get_settings

    get_settings.cache_clear()
    if appdb._engine is not None:
        appdb._engine.dispose()
    appdb._engine = appdb._SessionLocal = None
    yield url
    with admin.connect() as c:
        c.execute(text(f"drop database if exists {TEST_DB} with (force)"))


@pytest.fixture(scope="session")
def migrated(test_db_url):
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
    command.upgrade(cfg, "head")
    return test_db_url


@pytest.fixture()
def session(migrated):
    from app.db import session_factory

    with session_factory()() as s:
        yield s


@pytest.fixture(scope="session")
def loaded(migrated):
    """Ingest the real CSV once for the API tests."""
    from app.db import session_factory
    from app.services.ingest_yahoo import ingest_yahoo_csv

    with session_factory()() as s:
        run = ingest_yahoo_csv(s, REAL_CSV)
        assert run.status == "succeeded"
    return run.id
