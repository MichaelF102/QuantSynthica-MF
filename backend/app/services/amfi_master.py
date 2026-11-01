"""Load the official scheme register (AMFI latest-NAV file) into `amfi_schemes`."""
from __future__ import annotations

import gzip
import hashlib
import logging
from datetime import UTC, datetime
from pathlib import Path

from data_pipeline.sources import amfi
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AmfiScheme, IngestionRun

log = logging.getLogger(__name__)
SOURCE = "amfi_navall"


def ingest_nav_all(session: Session, *, body: bytes | None = None, records: list[amfi.AmfiRecord] | None = None) -> IngestionRun:
    """Fetch (or accept) the file, keep the raw bytes in bronze, upsert the register. Same file twice is a no-op."""
    if body is None:
        body, records = amfi.fetch_nav_all()
    elif records is None:
        records = list(amfi.parse(body.decode("utf-8", errors="replace")))
    sha = hashlib.sha256(body).hexdigest()

    prior = session.scalars(
        select(IngestionRun).where(IngestionRun.source == SOURCE, IngestionRun.file_sha256 == sha, IngestionRun.status == "succeeded")
    ).first()
    if prior is not None:
        run = IngestionRun(source=SOURCE, file_name="NAVAll.txt", file_sha256=sha, status="skipped", rows_read=len(records),
                           finished_at=datetime.now(UTC), summary={"reason": "identical file already ingested", "prior_run_id": prior.id})
        session.add(run)
        session.commit()
        return run

    bronze = Path(get_settings().data_dir) / "bronze" / "amfi"
    bronze.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    (bronze / f"NAVAll_{stamp}_{sha[:8]}.txt.gz").write_bytes(gzip.compress(body))

    run = IngestionRun(source=SOURCE, file_name="NAVAll.txt", file_sha256=sha, rows_read=len(records))
    session.add(run)
    session.commit()
    try:
        existing = {a.code: a for a in session.scalars(select(AmfiScheme))}
        dates = []
        for r in records:
            nd = datetime.combine(r.nav_date, datetime.min.time()) if r.nav_date else None
            dates.append(r.nav_date)
            row = existing.get(r.code)
            vals = dict(name=r.name, plan=r.plan, option=r.option, isin_primary=r.isin_primary, isin_reinvest=r.isin_reinvest,
                        amc=r.amc, category=r.category, latest_nav=r.nav, latest_nav_date=nd, last_seen_run_id=run.id)
            if row is None:
                session.add(AmfiScheme(code=r.code, **vals))
                run.schemes_inserted += 1
            else:
                changed = any(getattr(row, k) != v for k, v in vals.items() if k != "last_seen_run_id")
                for k, v in vals.items():
                    setattr(row, k, v)
                if changed:
                    run.schemes_updated += 1
                else:
                    run.schemes_unchanged += 1
        known = [d for d in dates if d]
        run.summary = {
            "records": len(records), "distinct_codes": len({r.code for r in records}),
            "latest_nav_date": max(known).isoformat() if known else None,
            "future_dated": sum(1 for d in known if d > datetime.now(UTC).date()),
            "nav_missing": sum(1 for r in records if r.nav is None),
        }
        run.status = "succeeded"
        run.finished_at = datetime.now(UTC)
        session.commit()
    except Exception as exc:
        session.rollback()
        run = session.get(IngestionRun, run.id)
        run.status, run.error, run.finished_at = "failed", repr(exc)[:2000], datetime.now(UTC)
        session.commit()
        raise
    log.info("amfi master ingested", extra={"run_id": run.id, "records": len(records)})
    return run
