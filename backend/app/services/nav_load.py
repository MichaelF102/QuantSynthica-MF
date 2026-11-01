"""Backfill and refresh NAV history for official scheme codes. Resumable and idempotent."""
from __future__ import annotations

import gzip
import logging
import time
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from data_pipeline.nav.quality import check_series
from data_pipeline.nav.store import NavStore
from data_pipeline.sources import mfapi
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AmfiScheme, DataQualityIssue, IngestionRun, NavCoverage

log = logging.getLogger(__name__)
SOURCE = "mfapi_history"


def nav_store() -> NavStore:
    return NavStore(Path(get_settings().data_dir) / "silver" / "nav")


def _fetch_one(code: str, delay: float):
    try:
        h = mfapi.fetch_scheme_history(code)
        time.sleep(delay)
        return code, h, None
    except Exception as exc:  # network/validation failure is recorded per scheme, not fatal
        return code, None, repr(exc)[:480]


def backfill(session: Session, codes: Iterable[str], *, workers: int = 3, delay: float = 0.15, refresh_after_days: int | None = None,
             limit: int | None = None) -> IngestionRun:
    """Load full history for `codes` that are not yet loaded (or older than `refresh_after_days`)."""
    codes = list(dict.fromkeys(codes))
    cov = {c.amfi_code: c for c in session.scalars(select(NavCoverage))}
    cutoff = date.today() - timedelta(days=refresh_after_days) if refresh_after_days is not None else None

    def needed(code: str) -> bool:
        c = cov.get(code)
        if c is None or c.status == "failed":
            return True
        return cutoff is not None and (c.last_date is None or c.last_date.date() < cutoff)

    todo = [c for c in codes if needed(c)]
    if limit:
        todo = todo[:limit]
    run = IngestionRun(source=SOURCE, file_name=f"{len(todo)} schemes", file_sha256="-", rows_read=len(todo))
    session.add(run)
    session.commit()

    store = nav_store()
    bronze = Path(get_settings().data_dir) / "bronze" / "mfapi"
    bronze.mkdir(parents=True, exist_ok=True)
    totals = {"inserted": 0, "updated": 0, "unchanged": 0, "failed": 0, "empty": 0, "issues": 0}
    t0 = time.time()

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_fetch_one, c, delay) for c in todo]
        for n, fut in enumerate(as_completed(futures), 1):
            code, hist, err = fut.result()
            row = cov.get(code) or NavCoverage(amfi_code=code, source="mfapi.in")
            if hist is None:
                row.status, row.error = "failed", err
                totals["failed"] += 1
            else:
                (bronze / f"{code}.json.gz").write_bytes(gzip.compress(hist.raw))
                clean, issues = check_series([(d, v) for d, v, _ in hist.observations])
                for i in issues:
                    if i.severity != "info":
                        session.add(DataQualityIssue(ingestion_run_id=run.id, symbol=code, rule=i.rule, severity=i.severity, detail=i.detail))
                totals["issues"] += sum(1 for i in issues if i.severity != "info")
                if not clean:
                    row.status, row.n_obs, row.n_issues = "empty", 0, len(issues)
                    totals["empty"] += 1
                else:
                    counts = store.upsert((code, d, v, "mfapi.in") for d, v in clean)
                    for k in ("inserted", "updated", "unchanged"):
                        totals[k] += counts[k]
                    row.status, row.error = "ok", None
                    row.first_date = datetime.combine(clean[0][0], datetime.min.time())
                    row.last_date = datetime.combine(clean[-1][0], datetime.min.time())
                    row.n_obs, row.n_issues = len(clean), len(issues)
                row.loaded_at = datetime.now(UTC)
            session.merge(row)
            if n % 100 == 0:
                session.commit()
                log.info("nav backfill progress", extra={"done": n, "of": len(todo), "elapsed_s": round(time.time() - t0)})
    run.status = "succeeded"
    run.finished_at = datetime.now(UTC)
    run.snapshots_inserted = totals["inserted"]
    run.summary = {**totals, "requested": len(todo), "skipped_already_loaded": len(codes) - len(todo), "seconds": round(time.time() - t0)}
    session.commit()
    return run


def refresh_coverage(session: Session, codes: Iterable[str] | None = None, source: str = "store") -> int:
    """Rebuild nav_coverage rows from what is actually in the store (first/last date, count)."""
    summ = nav_store().summary(codes)
    known = {c for c in session.scalars(select(AmfiScheme.code))}
    existing = {c.amfi_code: c for c in session.scalars(select(NavCoverage))}
    n = 0
    for code, (first, last, count) in summ.items():
        if code not in known:
            continue
        row = existing.get(code) or NavCoverage(amfi_code=code, source=source)
        row.first_date = datetime.combine(first, datetime.min.time())
        row.last_date = datetime.combine(last, datetime.min.time())
        row.n_obs, row.status, row.error = count, "ok", None
        row.loaded_at = datetime.now(UTC)
        session.merge(row)
        n += 1
    session.commit()
    return n


def official_recent_load(session: Session, start: date, end: date, *, codes: set[str] | None = None) -> IngestionRun:
    """Load every scheme's NAVs for [start, end] from the official history report (90-day windows).

    `codes=None` keeps all codes present in the scheme register. Raw windows are kept in bronze.
    """
    known = codes if codes is not None else set(session.scalars(select(AmfiScheme.code)))
    run = IngestionRun(source="amfi_history", file_name=f"{start}..{end}", file_sha256="-")
    session.add(run)
    session.commit()
    store = nav_store()
    bronze = Path(get_settings().data_dir) / "bronze" / "amfi"
    bronze.mkdir(parents=True, exist_ok=True)
    totals = {"inserted": 0, "updated": 0, "unchanged": 0, "records": 0, "windows": 0, "skipped_codes": 0, "disagreements": 0}
    t0 = time.time()
    from data_pipeline.sources import amfi

    for frm, to in amfi.history_windows(start, end):
        body, records = amfi.fetch_history(frm, to)
        (bronze / f"history_{frm}_{to}.txt.gz").write_bytes(gzip.compress(body))
        rows, skipped = [], set()
        for r in records:
            if r.nav is None or r.nav_date is None or r.nav <= 0:
                continue
            if r.code in known:
                rows.append((r.code, r.nav_date, r.nav, "amfi"))
            else:
                skipped.add(r.code)
        counts = store.upsert(rows)
        totals["windows"] += 1
        totals["records"] += len(records)
        totals["skipped_codes"] += len(skipped)
        for k in ("inserted", "updated", "unchanged"):
            totals[k] += counts[k]
        totals["disagreements"] += counts["updated"]  # same (code, date) already stored with a different NAV
        log.info("official window loaded", extra={"from": str(frm), "to": str(to), **counts})
    run.status, run.finished_at = "succeeded", datetime.now(UTC)
    run.snapshots_inserted = totals["inserted"]
    run.summary = {**totals, "seconds": round(time.time() - t0), "start": start.isoformat(), "end": end.isoformat()}
    session.commit()
    refresh_coverage(session, source="amfi")
    return run


def rebuild_store(session: Session) -> dict[str, int]:
    """Recreate the silver NAV store from bronze files only (no network). Official windows are applied last and win."""
    import shutil

    from data_pipeline.sources import amfi

    root = Path(get_settings().data_dir)
    shutil.rmtree(root / "silver" / "nav", ignore_errors=True)
    store = nav_store()
    known = set(session.scalars(select(AmfiScheme.code)))
    n = {"mfapi_files": 0, "official_windows": 0, "rows": 0}
    for f in sorted((root / "bronze" / "mfapi").glob("*.json.gz")):
        h = mfapi.parse_history(f.name.split(".")[0], gzip.decompress(f.read_bytes()))
        clean, _ = check_series([(d, v) for d, v, _ in h.observations])
        n["rows"] += sum(store.upsert((h.code, d, v, "mfapi.in") for d, v in clean).values())
        n["mfapi_files"] += 1
    for f in sorted((root / "bronze" / "amfi").glob("history_*.txt.gz")):
        recs = amfi.parse(gzip.decompress(f.read_bytes()).decode("utf-8", errors="replace"))
        rows = [(r.code, r.nav_date, r.nav, "amfi") for r in recs if r.code in known and r.nav and r.nav > 0 and r.nav_date]
        n["rows"] += sum(store.upsert(rows).values())
        n["official_windows"] += 1
    session.execute(text("delete from nav_coverage"))
    session.commit()
    n["coverage_rows"] = refresh_coverage(session, source="rebuild")
    return n
