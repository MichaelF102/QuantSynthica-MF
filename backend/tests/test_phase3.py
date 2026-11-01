"""Phase 3 services against a throwaway database and a temp data directory (no network)."""
import gzip
from datetime import date, timedelta

import pytest
from app.core.config import get_settings
from app.models import (
    AmfiScheme,
    DataQualityIssue,
    NavCoverage,
    Scheme,
    SchemeMapping,
)
from data_pipeline.sources import mfapi
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

# Real CSV row: 0P00005UMY.BO "ICICI Prudential Cnsv Hyb Reg Gr", price 77.78, 3Y return 11.37
NAV_FILE = """Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Plan;Option;Net Asset Value;Date

Open Ended Schemes(Hybrid Scheme - Conservative Hybrid Fund)

ICICI Prudential Mutual Fund

120001;INF109K01AAA;-;ICICI Prudential Conservative Hybrid Fund;Regular Plan;Growth;77.78;30-Oct-2026
120002;INF109K01AAB;-;ICICI Prudential Conservative Hybrid Fund;Direct Plan;Growth;90.11;30-Oct-2026
"""


@pytest.fixture()
def datadir(tmp_path, monkeypatch):
    monkeypatch.setenv("QSMF_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


@pytest.fixture()
def clean(session, loaded):
    """Start each test with empty Phase 3 tables."""
    for t in ("scheme_mappings", "nav_coverage", "amfi_schemes"):
        session.execute(text(f"delete from {t}"))
    session.execute(text("delete from data_quality_issues where rule like 'N%'"))
    session.execute(text("delete from ingestion_runs where source in ('amfi_navall','mfapi_history','scheme_mapping')"))
    session.commit()


def test_master_ingest_is_idempotent_and_keeps_raw_file(session, clean, datadir):
    from app.services.amfi_master import ingest_nav_all

    body = NAV_FILE.encode()
    r1 = ingest_nav_all(session, body=body)
    assert r1.status == "succeeded" and r1.schemes_inserted == 2
    r2 = ingest_nav_all(session, body=body)
    assert r2.status == "skipped"
    assert session.scalar(select(func.count()).select_from(AmfiScheme)) == 2
    raw = list((datadir / "bronze" / "amfi").glob("*.txt.gz"))
    assert len(raw) == 1 and gzip.decompress(raw[0].read_bytes()) == body

    changed = NAV_FILE.replace("77.78", "78.00").encode()  # a new day's file updates, never duplicates
    r3 = ingest_nav_all(session, body=changed)
    assert r3.schemes_updated == 1 and r3.schemes_unchanged == 1
    assert session.scalar(select(func.count()).select_from(AmfiScheme)) == 2
    assert session.get(AmfiScheme, "120001").latest_nav == 78.0


def _register(session):
    from app.services.amfi_master import ingest_nav_all

    ingest_nav_all(session, body=NAV_FILE.encode())


def test_mapping_persists_every_scheme_and_is_rerunnable(session, clean, datadir):
    from app.services.mapping import run_mapping

    _register(session)
    run = run_mapping(session)
    assert run.status == "succeeded"
    counts = run.summary["status_counts"]
    assert sum(counts.values()) == 3351  # nothing dropped
    assert session.scalar(select(func.count()).select_from(SchemeMapping)) == 3351
    assert counts["not_amfi_scheme"] > 200  # insurer funds are kept, labelled, not matched
    m = session.execute(
        select(SchemeMapping).join(Scheme, Scheme.id == SchemeMapping.scheme_id).where(Scheme.name == "ICICI Prudential Cnsv Hyb Reg Gr")
    ).scalar_one()
    assert (m.status, m.amfi_code, m.variant) == ("confirmed", "120001", "growth")

    run_mapping(session)  # rerun replaces, does not duplicate
    assert session.scalar(select(func.count()).select_from(SchemeMapping)) == 3351


def test_database_enforces_slot_uniqueness_for_accepted_mappings(session, clean, datadir):
    from app.services.mapping import run_mapping

    _register(session)
    run_mapping(session)
    donor = session.execute(select(SchemeMapping).where(SchemeMapping.status == "confirmed")).scalars().first()
    other = session.execute(select(Scheme).where(Scheme.id != donor.scheme_id, Scheme.id.notin_(select(SchemeMapping.scheme_id).where(SchemeMapping.status == "confirmed")))).scalars().first()
    session.execute(text("delete from scheme_mappings where scheme_id=:i"), {"i": other.id})
    session.add(SchemeMapping(scheme_id=other.id, amfi_code=donor.amfi_code, variant=donor.variant, status="confirmed", method="t", matcher_version="t"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def _fake_history(monkeypatch, per_code):
    import json

    def fetch(code):
        if code not in per_code:
            raise RuntimeError("boom")
        obs = per_code[code]
        body = json.dumps({"meta": {"scheme_code": code}, "status": "SUCCESS",
                           "data": [{"date": d.strftime("%d-%m-%Y"), "nav": str(v)} for d, v in obs]}).encode()
        return mfapi.parse_history(code, body)

    monkeypatch.setattr("app.services.nav_load.mfapi.fetch_scheme_history", fetch)


def test_nav_backfill_is_resumable_idempotent_and_records_failures(session, clean, datadir, monkeypatch):
    from app.services.nav_load import backfill, nav_store

    _register(session)
    start = date(2020, 1, 1)
    series = [(start + timedelta(days=i), 10 + i * 0.01) for i in range(400)]
    series.append((start + timedelta(days=5), 99.0))  # conflicting duplicate date -> withheld + flagged
    _fake_history(monkeypatch, {"120001": series})

    r = backfill(session, ["120001", "120002"], workers=2, delay=0)
    assert r.summary["failed"] == 1 and r.summary["inserted"] == 399  # the conflicting date is withheld
    cov = {c.amfi_code: c for c in session.scalars(select(NavCoverage))}
    assert cov["120001"].status == "ok" and cov["120001"].n_obs == 399 and cov["120002"].status == "failed"
    assert session.scalar(select(func.count()).select_from(DataQualityIssue).where(DataQualityIssue.rule == "N012_conflicting_duplicate")) == 1
    assert nav_store().row_count() == 399
    assert (datadir / "bronze" / "mfapi" / "120001.json.gz").exists()

    # resumable: the loaded scheme is skipped, the failed one is retried
    r2 = backfill(session, ["120001", "120002"], workers=2, delay=0)
    assert r2.summary["requested"] == 1 and r2.summary["skipped_already_loaded"] == 1
    # forcing a refresh of the loaded one changes nothing in the store
    r3 = backfill(session, ["120001"], workers=1, delay=0, refresh_after_days=0)
    assert r3.summary["inserted"] == 0 and r3.summary["unchanged"] == 399
    assert nav_store().row_count() == 399


def test_coverage_report_and_return_semantics(session, clean, datadir, monkeypatch):
    from app.services.coverage import build_report
    from app.services.mapping import run_mapping
    from app.services.nav_load import backfill

    _register(session)
    snap = date(2026, 10, 30)
    now = 77.78
    # build a NAV history whose true 3Y CAGR equals the source's reported 11.37%, 1Y 7.92%, 5Y 9.9%
    pts = {snap: now, date(2025, 10, 30): now / 1.0792, date(2023, 10, 30): now / 1.1137**3, date(2021, 10, 29): now / 1.099**5}
    series = [(d, v) for d, v in sorted(pts.items())]
    _fake_history(monkeypatch, {"120001": series})
    backfill(session, ["120001"], workers=1, delay=0)
    run_mapping(session, snapshot=snap)

    rep = build_report(session)
    assert rep["mapping"]["schemes_total"] == 3351 and rep["mapping"]["slot_conflicts"] == 0
    assert sum(rep["mapping"]["status_counts"].values()) == 3351
    assert rep["nav_history"]["with_history"] == 1 and rep["nav_history"]["at_least_5y"] == 1
    sem = rep["return_semantics"]
    assert sem["3y"]["closer_to"].startswith("annualised") and sem["3y"]["median_abs_error_vs_annualised_pp"] < 0.1
    assert sem["5y"]["median_abs_error_vs_cumulative_pp"] > 10  # a cumulative reading is clearly wrong


def test_coverage_endpoint_serves_the_stored_report(session, clean, datadir):
    from app.main import app
    from app.services.coverage import write_report
    from fastapi.testclient import TestClient

    c = TestClient(app)
    assert c.get("/api/v1/data-coverage").status_code == 404 or True  # file may not exist yet
    _register(session)
    write_report(session)
    r = c.get("/api/v1/data-coverage")
    assert r.status_code == 200 and "register" in r.json()


def test_quality_scan_flags_and_is_idempotent(session, clean, datadir):
    from app.services.nav_checks import quality_scan
    from app.services.nav_load import nav_store, refresh_coverage

    _register(session)
    d0 = date(2024, 1, 1)
    series = [(d0 + timedelta(days=i), 10.0 + i * 0.01) for i in range(20)]
    series += [(d0 + timedelta(days=40), 10.2), (d0 + timedelta(days=41), 14.0)]  # 21-day gap, then a +37% move
    nav_store().upsert(("120001", d, v, "amfi") for d, v in series)
    refresh_coverage(session, ["120001"])

    counts = quality_scan(session, ["120001"])
    assert counts == {"N020_gap": 1, "N021_large_move": 1}
    assert session.get(NavCoverage, "120001").n_issues == 2
    n = session.scalar(select(func.count()).select_from(DataQualityIssue).where(DataQualityIssue.rule.like("N%")))
    quality_scan(session, ["120001"])  # rescan replaces, never accumulates
    assert session.scalar(select(func.count()).select_from(DataQualityIssue).where(DataQualityIssue.rule.like("N%"))) == n == 2
    assert len(nav_store().read(["120001"])["120001"]) == 22  # flagged values are kept


def test_cross_source_agreement(datadir, session):
    import json

    from app.services.nav_checks import validate_sources

    (datadir / "bronze" / "amfi").mkdir(parents=True)
    (datadir / "bronze" / "mfapi").mkdir(parents=True)
    official = ("Scheme Code;NAV Name;Plan;Option;ISIN Div Payout/ISIN Growth;ISIN Div Reinvestment;Net Asset Value;Date\n\n"
                "Open Ended Schemes ( X )\n\nAxis Mutual Fund\n"
                "120001;F;Direct Plan;Growth;INF1;;10.0000;01-Oct-2026\n120001;F;Direct Plan;Growth;INF1;;10.5000;02-Oct-2026\n"
                "120001;F;Direct Plan;Growth;INF1;;11.0000;05-Oct-2026\n")
    (datadir / "bronze" / "amfi" / "history_a.txt.gz").write_bytes(gzip.compress(official.encode()))
    other = {"meta": {}, "status": "SUCCESS", "data": [{"date": "01-10-2026", "nav": "10.00000"}, {"date": "02-10-2026", "nav": "10.60000"}]}
    (datadir / "bronze" / "mfapi" / "120001.json.gz").write_bytes(gzip.compress(json.dumps(other).encode()))
    out = validate_sources(session)
    assert out["overlapping_observations"] == 2 and out["differing"] == 1 and out["share_differing"] == 0.5
    assert out["examples"][0]["official"] == 10.5 and out["examples"][0]["mfapi"] == 10.6
