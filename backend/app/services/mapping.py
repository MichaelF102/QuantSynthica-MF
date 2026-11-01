"""Run the source -> official-scheme matcher against the database and persist the result."""
from __future__ import annotations

import csv
import logging
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from data_pipeline.mapping.matcher import (
    MATCHER_VERSION,
    SourceFund,
    build_amc_map,
    candidates_for,
    estimate_snapshot_date,
    index_amfi,
    match_all,
    top_candidate_codes,
)
from data_pipeline.sources.amfi import AmfiRecord
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (
    AMC,
    AmfiScheme,
    ExternalId,
    FundCategory,
    FundSnapshot,
    IngestionRun,
    NavCoverage,
    Scheme,
    SchemeMapping,
)
from app.services.nav_load import nav_store

log = logging.getLogger(__name__)
HISTORY_WINDOW_DAYS = 400


def latest_source_run(session: Session) -> IngestionRun | None:
    return session.scalars(
        select(IngestionRun).where(IngestionRun.source == "yahoo_csv", IngestionRun.status == "succeeded").order_by(IngestionRun.id.desc())
    ).first()


def load_source_funds(session: Session, run_id: int) -> tuple[list[SourceFund], dict[str, int]]:
    rows = session.execute(
        select(Scheme.id, ExternalId.value, Scheme.name, AMC.name, FundCategory.name, Scheme.plan_type, Scheme.option_type,
               Scheme.idcw_mode, Scheme.idcw_freq, FundSnapshot.price, Scheme.is_insurer_fund)
        .join(ExternalId, (ExternalId.scheme_id == Scheme.id) & (ExternalId.id_type == "yahoo_symbol"))
        .join(AMC, AMC.id == Scheme.amc_id).join(FundCategory, FundCategory.id == Scheme.category_id)
        .join(FundSnapshot, (FundSnapshot.scheme_id == Scheme.id) & (FundSnapshot.ingestion_run_id == run_id))
    ).all()
    funds, ids = [], {}
    for sid, sym, name, amc, cat, plan, opt, mode, freq, price, ins in rows:
        funds.append(SourceFund(sym, name, amc, cat, plan, opt, mode, freq, price, ins))
        ids[sym] = sid
    return funds, ids


def load_amfi_records(session: Session) -> list[AmfiRecord]:
    return [
        AmfiRecord(a.code, a.name, a.plan, a.option, a.isin_primary, a.isin_reinvest, a.latest_nav,
                   a.latest_nav_date.date() if a.latest_nav_date else None, a.amc, a.category)
        for a in session.scalars(select(AmfiScheme))
    ]


def _read_overrides(name: str, key: str, val: str) -> dict[str, str]:
    path = Path(get_settings().data_dir) / "reference" / name
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as fh:
        return {r[key]: r[val] for r in csv.DictReader(fh) if r.get(key)}


ACTIVE_WITHIN_DAYS = 45


def candidate_codes(session: Session, k: int = 3) -> set[str]:
    """Codes whose NAV history is worth fetching: best name candidates that are still being published.

    Schemes whose latest NAV is older than ACTIVE_WITHIN_DAYS (closed or merged) cannot be the funds in a
    current snapshot; they are skipped here and handled by a later survivorship-bias task.
    """
    run = latest_source_run(session)
    funds, _ = load_source_funds(session, run.id)
    records = load_amfi_records(session)
    newest = max((r.nav_date for r in records if r.nav_date), default=None)
    if newest is not None:
        records = [r for r in records if r.nav_date and (newest - r.nav_date).days <= ACTIVE_WITHIN_DAYS]
    return top_candidate_codes(funds, records, k=k, amc_overrides=_read_overrides("amc_overrides.csv", "source_amc", "amfi_amc"))


def _window(session: Session, codes: set[str], end: date) -> dict[str, dict[date, float]]:
    have = {c for c in session.scalars(select(NavCoverage.amfi_code).where(NavCoverage.status == "ok"))}
    series = nav_store().read(codes & have, start=end - timedelta(days=HISTORY_WINDOW_DAYS), end=end)
    return {c: dict(v) for c, v in series.items()}


def estimate_snapshot(session: Session, funds: list[SourceFund], records: list[AmfiRecord], amc_overrides) -> tuple[date | None, int, int]:
    """Use near-certain name matches to find the date on which source prices equal official NAVs."""
    by_amc = index_amfi(records)
    amc_map = build_amc_map((f.amc for f in funds), by_amc.keys(), amc_overrides)
    chosen: dict[str, float] = {}
    for f in funds:
        a = amc_map.get(f.amc)
        if a is None or f.price is None or f.option_type != "Growth" or f.plan_type == "Unspecified":
            continue
        cands = candidates_for(f, by_amc[a])
        top = [c for c in cands if c.name_score >= 0.95]
        if len(top) == 1:
            chosen[top[0].amfi_code] = f.price
    end = max((r.nav_date for r in records if r.nav_date), default=date.today())
    hist = _window(session, set(chosen), end)
    pairs = [(chosen[c], h) for c, h in hist.items()]
    return estimate_snapshot_date(pairs)


def run_mapping(session: Session, *, snapshot: date | None = None) -> IngestionRun:
    src_run = latest_source_run(session)
    if src_run is None:
        raise RuntimeError("no source snapshot ingested")
    funds, ids = load_source_funds(session, src_run.id)
    records = load_amfi_records(session)
    if not records:
        raise RuntimeError("official scheme register is empty; run the master ingest first")
    amc_ov = _read_overrides("amc_overrides.csv", "source_amc", "amfi_amc")
    code_ov = _read_overrides("mapping_overrides.csv", "symbol", "amfi_code")

    run = IngestionRun(source="scheme_mapping", file_name=f"matcher {MATCHER_VERSION}", file_sha256="-", rows_read=len(funds))
    session.add(run)
    session.commit()

    est = (snapshot, 0, 0)
    if snapshot is None:
        est = estimate_snapshot(session, funds, records, amc_ov)
    snap = est[0]
    nav_lookup = None
    if snap is not None:
        codes = top_candidate_codes(funds, records, k=5, min_name=0.5, amc_overrides=amc_ov)
        hist = _window(session, codes, snap)
        nav_lookup = lambda code: hist.get(code)
    results, amc_map = match_all(funds, records, amc_overrides=amc_ov, code_overrides=code_ov, nav_lookup=nav_lookup, snapshot=snap)

    session.execute(delete(SchemeMapping).where(SchemeMapping.scheme_id.in_(list(ids.values()))))
    for m in results:
        session.add(SchemeMapping(
            scheme_id=ids[m.symbol], amfi_code=m.amfi_code, variant=m.variant, status=m.status, name_score=m.name_score,
            nav_tier=m.nav_tier, nav_diff=m.nav_diff,
            evidence_date=datetime.combine(m.evidence_date, datetime.min.time()) if m.evidence_date else None,
            method=m.method, matcher_version=MATCHER_VERSION, alternatives=m.alternatives or None, run_id=run.id,
        ))
    if snap is not None and est[1] >= 30:
        src_run.source_asof = datetime.combine(snap, datetime.min.time(), tzinfo=UTC)
    run.status = "succeeded"
    run.finished_at = datetime.now(UTC)
    run.summary = {
        "matcher_version": MATCHER_VERSION,
        "status_counts": dict(Counter(m.status for m in results)),
        "snapshot_date_estimate": snap.isoformat() if snap else None,
        "snapshot_votes": est[1], "snapshot_pairs": est[2],
        "unmatched_amcs": sorted(a for a, v in amc_map.items() if v is None),
    }
    session.commit()
    log.info("mapping complete", extra=run.summary)
    return run
