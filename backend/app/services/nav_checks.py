"""Checks over the stored NAV data: per-series quality scan and cross-source agreement."""
from __future__ import annotations

import gzip
import json
import statistics
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from data_pipeline.nav.quality import check_series
from data_pipeline.sources import amfi, mfapi
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import DataQualityIssue, IngestionRun, NavCoverage, SchemeMapping
from app.services.nav_load import nav_store

ACCEPTED = ("confirmed", "probable", "name_only")


def accepted_codes(session: Session) -> list[str]:
    return sorted({c for c in session.scalars(select(SchemeMapping.amfi_code).where(SchemeMapping.status.in_(ACCEPTED))) if c})


def quality_scan(session: Session, codes: list[str] | None = None, batch: int = 250) -> dict[str, int]:
    """Run the series checks on every accepted scheme. Idempotent: previous N-rule issues for a code are replaced."""
    codes = codes if codes is not None else accepted_codes(session)
    run = IngestionRun(source="nav_quality", file_name=f"{len(codes)} schemes", file_sha256="-", rows_read=len(codes))
    session.add(run)
    session.commit()
    store = nav_store()
    counts: Counter = Counter()
    for i in range(0, len(codes), batch):
        part = codes[i : i + batch]
        series = store.read(part)
        session.execute(delete(DataQualityIssue).where(DataQualityIssue.symbol.in_(part), DataQualityIssue.rule.like("N%")))
        cov = {c.amfi_code: c for c in session.scalars(select(NavCoverage).where(NavCoverage.amfi_code.in_(part)))}
        for code in part:
            clean, issues = check_series(series.get(code, []))
            real = [x for x in issues if x.severity != "info"]
            for x in real:
                session.add(DataQualityIssue(ingestion_run_id=run.id, symbol=code, rule=x.rule, severity=x.severity, detail=x.detail))
                counts[x.rule] += 1
            if code in cov:
                cov[code].n_issues = len(real)
        session.commit()
    run.status, run.finished_at = "succeeded", datetime.now(UTC)
    run.summary = {"schemes": len(codes), "issues_by_rule": dict(counts)}
    session.commit()
    return dict(counts)


def agreement_path() -> Path:
    return Path(get_settings().data_dir) / "gold" / "source_agreement.json"


def validate_sources(session: Session) -> dict:
    """Compare the two NAV sources on every (code, date) both provided, using the raw bronze files."""
    root = Path(get_settings().data_dir) / "bronze"
    m_series: dict[str, dict] = {}
    for f in (root / "mfapi").glob("*.json.gz"):
        h = mfapi.parse_history(f.name.split(".")[0], gzip.decompress(f.read_bytes()))
        m_series[h.code] = {d: v for d, v, _ in h.observations if v is not None}
    overlap = diff = 0
    rel: list[float] = []
    examples: list[dict] = []
    codes_compared: set[str] = set()
    for f in sorted((root / "amfi").glob("history_*.txt.gz")):
        for r in amfi.parse(gzip.decompress(f.read_bytes()).decode("utf-8", errors="replace")):
            ms = m_series.get(r.code)
            if ms is None or r.nav is None or r.nav_date is None:
                continue
            other = ms.get(r.nav_date)
            if other is None:
                continue
            overlap += 1
            codes_compared.add(r.code)
            if abs(other - r.nav) > 1e-9:
                diff += 1
                rel.append(abs(other - r.nav) / r.nav)
                if len(examples) < 10:
                    examples.append({"code": r.code, "date": r.nav_date.isoformat(), "official": r.nav, "mfapi": other})
    out = {
        "generated_at": datetime.now(UTC).isoformat(),
        "codes_compared": len(codes_compared), "overlapping_observations": overlap, "differing": diff,
        "share_differing": round(diff / overlap, 5) if overlap else None,
        "median_relative_difference": statistics.median(rel) if rel else None,
        "max_relative_difference": max(rel) if rel else None, "examples": examples,
        "policy": "Where the sources disagree, the official file wins in the silver store.",
    }
    agreement_path().parent.mkdir(parents=True, exist_ok=True)
    agreement_path().write_text(json.dumps(out, indent=2))
    return out
