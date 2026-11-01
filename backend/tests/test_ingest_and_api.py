from app.models import (
    AMC,
    ExternalId,
    FundCategory,
    FundFamily,
    FundSnapshot,
    IngestionRun,
    Scheme,
)
from app.services.ingest_yahoo import ingest_yahoo_csv
from sqlalchemy import func, select

from tests.conftest import REAL_CSV


def test_ingest_counts(session, loaded):
    assert session.scalar(select(func.count()).select_from(Scheme)) == 3351
    assert session.scalar(select(func.count(func.distinct(ExternalId.value)))) == 3351
    assert session.scalar(select(func.count()).select_from(AMC)) == 55
    assert session.scalar(select(func.count()).select_from(FundCategory)) == 49
    assert session.scalar(select(func.count()).select_from(FundFamily)) == 1196
    assert session.scalar(select(func.count()).select_from(FundSnapshot)) == 3351


def test_unspecified_retained_not_guessed(session, loaded):
    assert session.scalar(select(func.count()).select_from(Scheme).where(Scheme.plan_type == "Unspecified")) == 975
    assert session.scalar(select(func.count()).select_from(Scheme).where(Scheme.option_type == "Unspecified")) == 415


def test_nulls_not_imputed(session, loaded):
    n = session.scalar(select(func.count()).select_from(FundSnapshot).where(FundSnapshot.net_assets.is_(None)))
    assert n == 1067


def test_split_not_in_features(session, loaded):
    snap = session.scalars(select(FundSnapshot).limit(1)).one()
    assert "split" not in snap.features and snap.audit["split"] in {"train", "test"}


def test_rerun_identical_file_is_noop(session, loaded):
    before = session.scalar(select(func.count()).select_from(FundSnapshot))
    run = ingest_yahoo_csv(session, REAL_CSV)
    assert run.status == "skipped"
    assert session.scalar(select(func.count()).select_from(FundSnapshot)) == before
    assert session.scalar(select(func.count()).select_from(Scheme)) == 3351


def test_forced_rerun_creates_no_duplicate_schemes(session, loaded):
    run = ingest_yahoo_csv(session, REAL_CSV, force=True)
    assert run.status == "succeeded"
    assert run.schemes_inserted == 0 and run.schemes_unchanged == 3351
    assert session.scalar(select(func.count()).select_from(Scheme)) == 3351
    assert session.scalar(select(func.count()).select_from(ExternalId)) == 3351
    assert session.scalar(select(func.count()).select_from(IngestionRun).where(IngestionRun.status == "failed")) == 0


def client():
    from app.main import app
    from fastapi.testclient import TestClient

    return TestClient(app)


def test_health(loaded):
    assert client().get("/api/v1/health").json() == {"status": "ok"}


def test_list_funds_paging_and_filters(loaded):
    c = client()
    r = c.get("/api/v1/funds", params={"page_size": 10}).json()
    assert r["total"] == 3351 and len(r["items"]) == 10
    r = c.get("/api/v1/funds", params={"asset_tier": "Equity", "plan_type": "Direct", "option_type": "Growth"}).json()
    assert r["total"] > 0 and all(i["asset_tier"] == "Equity" and i["plan_type"] == "Direct" for i in r["items"])
    r = c.get("/api/v1/funds", params={"plan_type": "Unspecified"}).json()
    assert r["total"] == 975


def test_sort_nulls_last_and_validation(loaded):
    c = client()
    items = c.get("/api/v1/funds", params={"sort": "net_assets", "order": "desc", "page_size": 5}).json()["items"]
    assert all(i["net_assets"] is not None for i in items)
    vals = [i["net_assets"] for i in items]
    assert vals == sorted(vals, reverse=True)
    assert c.get("/api/v1/funds", params={"sort": "drop table"}).status_code == 422
    assert c.get("/api/v1/funds", params={"page_size": 5000}).status_code == 422


def test_fund_detail(loaded):
    c = client()
    first = c.get("/api/v1/funds", params={"page_size": 1}).json()["items"][0]
    d = c.get(f"/api/v1/funds/{first['id']}").json()
    assert d["symbol"] == first["symbol"] and d["external_ids"]["yahoo_symbol"] == first["symbol"]
    assert "split" not in d["features"]
    assert c.get("/api/v1/funds/99999999").status_code == 404


def test_data_quality_endpoint(loaded):
    d = client().get("/api/v1/data-quality").json()
    assert d["rows_read"] == 3351 and d["summary"]["plan_unspecified"] == 975
    assert "unknown" in d["note"]
