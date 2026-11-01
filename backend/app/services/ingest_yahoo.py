"""Load the Yahoo CSV into PostgreSQL. Idempotent: re-ingesting an identical file is a no-op."""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from data_pipeline.ingestion.yahoo_csv import FundRow, parse_file, summarize
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AMC,
    DataQualityIssue,
    ExternalId,
    FundCategory,
    FundFamily,
    FundSnapshot,
    IngestionRun,
    Scheme,
)

log = logging.getLogger(__name__)
SOURCE = "yahoo_csv"
ID_TYPE = "yahoo_symbol"

_SCHEME_FIELDS = (
    "name", "asset_tier", "plan_type", "option_type", "idcw_mode", "idcw_freq",
    "is_insurer_fund", "is_discontinued", "n_share_classes",
)


def ingest_yahoo_csv(session: Session, path: Path, *, force: bool = False) -> IngestionRun:
    parsed = parse_file(path)

    if not force:
        prior = session.scalars(
            select(IngestionRun)
            .where(IngestionRun.file_sha256 == parsed.sha256, IngestionRun.status == "succeeded", IngestionRun.source == SOURCE)
            .order_by(IngestionRun.id.desc())
        ).first()
        if prior is not None:
            run = IngestionRun(
                source=SOURCE, file_name=path.name, file_sha256=parsed.sha256, status="skipped",
                rows_read=len(parsed.rows), finished_at=datetime.now(UTC),
                summary={"reason": "identical file already ingested", "prior_run_id": prior.id},
            )
            session.add(run)
            session.commit()
            log.info("ingest skipped: identical file", extra={"prior_run_id": prior.id, "sha256": parsed.sha256})
            return run

    run = IngestionRun(source=SOURCE, file_name=path.name, file_sha256=parsed.sha256, rows_read=len(parsed.rows))
    session.add(run)
    session.commit()  # persist the run row even if the load fails
    try:
        _load(session, run, parsed)
        run.status = "succeeded"
        run.finished_at = datetime.now(UTC)
        session.commit()
    except Exception as exc:
        session.rollback()
        run = session.get(IngestionRun, run.id)
        run.status = "failed"
        run.error = repr(exc)[:2000]
        run.finished_at = datetime.now(UTC)
        session.commit()
        log.exception("ingest failed", extra={"run_id": run.id})
        raise
    log.info(
        "ingest complete",
        extra={
            "run_id": run.id, "rows": run.rows_read, "inserted": run.schemes_inserted,
            "updated": run.schemes_updated, "unchanged": run.schemes_unchanged,
            "quarantined": run.rows_quarantined,
        },
    )
    return run


def _load(session: Session, run: IngestionRun, parsed) -> None:
    amcs = {a.name: a for a in session.scalars(select(AMC))}
    cats = {c.name: c for c in session.scalars(select(FundCategory))}
    fams = {(f.base_fund, f.amc_id): f for f in session.scalars(select(FundFamily))}
    by_symbol = {
        e.value: e.scheme
        for e in session.scalars(select(ExternalId).where(ExternalId.id_type == ID_TYPE, ExternalId.source == SOURCE))
    }

    def get_amc(row: FundRow) -> AMC:
        a = amcs.get(row.amc)
        if a is None:
            a = AMC(name=row.amc, is_insurer=row.is_insurer_fund)
            session.add(a)
            session.flush()
            amcs[row.amc] = a
        elif row.is_insurer_fund and not a.is_insurer:
            a.is_insurer = True
        return a

    for row in parsed.rows:
        amc = get_amc(row)
        cat = cats.get(row.category)
        if cat is None:
            cat = FundCategory(name=row.category)
            session.add(cat)
            session.flush()
            cats[row.category] = cat
        fam = None
        if row.base_fund:
            fam = fams.get((row.base_fund, amc.id))
            if fam is None:
                fam = FundFamily(base_fund=row.base_fund, amc_id=amc.id)
                session.add(fam)
                session.flush()
                fams[(row.base_fund, amc.id)] = fam

        scheme = by_symbol.get(row.symbol)
        wanted = {f: getattr(row, f) for f in _SCHEME_FIELDS}
        if scheme is None:
            scheme = Scheme(amc_id=amc.id, category_id=cat.id, family_id=fam.id if fam else None, **wanted)
            session.add(scheme)
            session.flush()
            session.add(ExternalId(scheme_id=scheme.id, id_type=ID_TYPE, value=row.symbol, source=SOURCE, ingestion_run_id=run.id))
            by_symbol[row.symbol] = scheme
            run.schemes_inserted += 1
        else:
            changed = False
            for f, v in wanted.items():
                if getattr(scheme, f) != v:
                    setattr(scheme, f, v)
                    changed = True
            for f, v in (("amc_id", amc.id), ("category_id", cat.id), ("family_id", fam.id if fam else None)):
                if getattr(scheme, f) != v:
                    setattr(scheme, f, v)
                    changed = True
            if changed:
                run.schemes_updated += 1
            else:
                run.schemes_unchanged += 1

        session.add(
            FundSnapshot(
                scheme_id=scheme.id, ingestion_run_id=run.id, source_rank=row.source_rank,
                quarantined=row.quarantined, features=row.features, audit=row.audit, **row.values,
            )
        )
        run.snapshots_inserted = (run.snapshots_inserted or 0) + 1
        if row.quarantined:
            run.rows_quarantined += 1
        for issue in row.issues:
            session.add(
                DataQualityIssue(
                    ingestion_run_id=run.id, scheme_id=scheme.id, symbol=row.symbol,
                    rule=issue.rule, severity=issue.severity, detail=issue.detail,
                )
            )

    for issue in parsed.file_issues:
        session.add(
            DataQualityIssue(
                ingestion_run_id=run.id, symbol=issue.symbol, rule=issue.rule,
                severity=issue.severity, detail=issue.detail,
            )
        )
    run.summary = summarize(parsed)
    session.flush()
