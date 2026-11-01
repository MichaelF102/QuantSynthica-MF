"""Mapping and NAV coverage report (stored as JSON; served by /api/v1/data-coverage)."""
from __future__ import annotations

import json
import statistics
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (
    AmfiScheme,
    DataQualityIssue,
    FundSnapshot,
    IngestionRun,
    NavCoverage,
    Scheme,
    SchemeMapping,
)
from app.services.mapping import latest_source_run
from app.services.nav_load import nav_store

ACCEPTED = ("confirmed", "probable", "name_only")


def report_path() -> Path:
    return Path(get_settings().data_dir) / "gold" / "coverage_report.json"


def _on_or_before(series: list[tuple[date, float]], target: date, max_back: int = 7) -> tuple[date, float] | None:
    best = None
    for d, v in series:
        if d <= target and (target - d).days <= max_back:
            best = (d, v)
        elif d > target:
            break
    return best


def _years_back(snap: date, years: int) -> date:
    try:
        return snap.replace(year=snap.year - years)
    except ValueError:  # 29 February
        return snap.replace(year=snap.year - years, day=28)


def return_semantics(session: Session, snap: date, run_id: int) -> dict[str, Any]:
    """Are the source's reported returns aligned to the snapshot date, and are multi-year figures annualised?

    Compares each reported return with the value computed from official NAVs ending on the snapshot date.
    Growth schemes with confirmed mappings only (IDCW payouts would distort NAV-based returns).
    """
    rows = session.execute(
        select(SchemeMapping.amfi_code, FundSnapshot.ytd_return, FundSnapshot.return_3m, FundSnapshot.return_1y,
               FundSnapshot.return_3y, FundSnapshot.return_5y)
        .join(Scheme, Scheme.id == SchemeMapping.scheme_id)
        .join(FundSnapshot, (FundSnapshot.scheme_id == Scheme.id) & (FundSnapshot.ingestion_run_id == run_id))
        .where(SchemeMapping.status == "confirmed", Scheme.option_type == "Growth", Scheme.is_insurer_fund.is_(False))
    ).all()
    codes = {r[0] for r in rows}
    store = nav_store()
    now = store.read(codes, start=snap - timedelta(days=7), end=snap)
    # (label, years for annualising or None for cumulative, start date, column index)
    specs = [
        ("ytd", None, date(snap.year - 1, 12, 31), 1),
        ("3m", None, snap - timedelta(days=91), 2),  # approximate 3 months; tolerance is wide enough
        ("1y", 1, _years_back(snap, 1), 3),
        ("3y", 3, _years_back(snap, 3), 4),
        ("5y", 5, _years_back(snap, 5), 5),
    ]
    out: dict[str, Any] = {"snapshot_date": snap.isoformat()}
    for label, years, start, idx in specs:
        then = store.read(codes, start=start - timedelta(days=7), end=start)
        err_cum, err_ann, n = [], [], 0
        for r in rows:
            code, reported = r[0], r[idx]
            if reported is None or code not in now or code not in then:
                continue
            a, b = _on_or_before(now[code], snap, 3), _on_or_before(then[code], start, 7)
            if not a or not b:
                continue
            n += 1
            cum = (a[1] / b[1] - 1) * 100
            err_cum.append(abs(reported - cum))
            if years:
                err_ann.append(abs(reported - ((a[1] / b[1]) ** (1 / years) - 1) * 100))
        if not n:
            continue
        mc = statistics.median(err_cum)
        entry: dict[str, Any] = {"funds_compared": n, "median_abs_error_vs_cumulative_pp": round(mc, 2),
                                 "share_within_1pp_cumulative": round(sum(e <= 1 for e in err_cum) / n, 3)}
        if years:
            ma = statistics.median(err_ann)
            entry.update(
                median_abs_error_vs_annualised_pp=round(ma, 2),
                share_within_1pp_annualised=round(sum(e <= 1 for e in err_ann) / n, 3),
                closer_to=("same (1-year: no difference)" if abs(ma - mc) < 1e-9
                           else "annualised (CAGR)" if ma < mc else "cumulative"),
            )
        best = entry.get("share_within_1pp_annualised", entry["share_within_1pp_cumulative"])
        entry["aligned_to_snapshot"] = best >= 0.9
        out[label] = entry
    return out


def build_report(session: Session) -> dict[str, Any]:
    src = latest_source_run(session)
    mrun = session.scalars(select(IngestionRun).where(IngestionRun.source == "scheme_mapping", IngestionRun.status == "succeeded")
                           .order_by(IngestionRun.id.desc())).first()
    arun = session.scalars(select(IngestionRun).where(IngestionRun.source == "amfi_navall", IngestionRun.status == "succeeded")
                           .order_by(IngestionRun.id.desc())).first()
    report: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "source_snapshot_run": src.id if src else None,
        "register": {"run_id": arun.id if arun else None, "summary": arun.summary if arun else None,
                     "schemes": session.scalar(select(func.count()).select_from(AmfiScheme))},
        "mapping_run": {"run_id": mrun.id if mrun else None, "summary": mrun.summary if mrun else None},
    }
    if mrun is None or src is None:
        report["note"] = "Mapping has not been run yet."
        return report

    rows = session.execute(
        select(Scheme.id, Scheme.asset_tier, Scheme.is_insurer_fund, Scheme.family_id, Scheme.plan_type, Scheme.option_type,
               SchemeMapping.status, SchemeMapping.amfi_code, SchemeMapping.variant, SchemeMapping.nav_tier)
        .join(SchemeMapping, SchemeMapping.scheme_id == Scheme.id)
    ).all()
    total = len(rows)
    by_status = Counter(r.status for r in rows)
    non_ins = [r for r in rows if not r.is_insurer_fund]
    by_tier: dict[str, Counter] = defaultdict(Counter)
    for r in non_ins:
        by_tier[r.asset_tier][r.status] += 1
    accepted = [r for r in non_ins if r.status in ACCEPTED]
    slots = Counter((r.amfi_code, r.variant) for r in accepted)

    cov = {c.amfi_code: c for c in session.scalars(select(NavCoverage))}
    def years(c: NavCoverage) -> float:
        return (c.last_date - c.first_date).days / 365.25 if c and c.first_date and c.last_date else 0.0
    hist = [cov.get(r.amfi_code) for r in accepted]
    confirmed = [r for r in non_ins if r.status == "confirmed"]
    fams_all = {r.family_id for r in non_ins if r.family_id}
    fams_mapped = {r.family_id for r in accepted if r.family_id}
    fams_dg_all = {r.family_id for r in non_ins if r.family_id and r.plan_type == "Direct" and r.option_type == "Growth"}
    fams_dg_ok = {r.family_id for r in accepted if r.family_id and r.plan_type == "Direct" and r.option_type == "Growth"}
    fams_dg_hist = {r.family_id for r, c in zip(accepted, hist) if r.family_id and r.plan_type == "Direct" and r.option_type == "Growth"
                    and c is not None and c.status == "ok" and years(c) >= 3}

    report["mapping"] = {
        "schemes_total": total,
        "status_counts": dict(by_status),
        "insurer_funds": sum(1 for r in rows if r.is_insurer_fund),
        "non_insurer_schemes": len(non_ins),
        "non_insurer_status_counts": dict(Counter(r.status for r in non_ins)),
        "by_asset_tier": {t: dict(c) for t, c in by_tier.items()},
        "accepted_share_non_insurer": round(len(accepted) / len(non_ins), 4) if non_ins else None,
        "confirmed_share_non_insurer": round(len(confirmed) / len(non_ins), 4) if non_ins else None,
        "distinct_official_codes_accepted": len({r.amfi_code for r in accepted}),
        "slot_conflicts": sum(1 for v in slots.values() if v > 1),
        "note": "A code may serve several source rows (IDCW payout and reinvestment). Uniqueness holds per (code, variant).",
    }
    report["families"] = {
        "non_insurer_families": len(fams_all), "families_with_accepted_mapping": len(fams_mapped),
        "families_with_direct_growth": len(fams_dg_all), "direct_growth_mapped": len(fams_dg_ok),
        "direct_growth_mapped_with_3y_history": len(fams_dg_hist),
    }
    ok = [c for c in hist if c is not None and c.status == "ok"]
    report["nav_history"] = {
        "accepted_schemes": len(accepted), "with_history": len(ok), "failed": sum(1 for c in hist if c is not None and c.status == "failed"),
        "not_loaded": sum(1 for c in hist if c is None),
        "at_least_1y": sum(1 for c in ok if years(c) >= 1), "at_least_3y": sum(1 for c in ok if years(c) >= 3),
        "at_least_5y": sum(1 for c in ok if years(c) >= 5), "at_least_10y": sum(1 for c in ok if years(c) >= 10),
        "observations_total": nav_store().row_count(), "with_quality_issues": sum(1 for c in ok if c.n_issues),
    }
    summ = mrun.summary or {}
    snap = summ.get("snapshot_date_estimate")
    report["snapshot_date"] = {
        "estimate": snap, "votes": summ.get("snapshot_votes"), "pairs_used": summ.get("snapshot_pairs"),
        "method": "Date on which most high-confidence source prices equal the official NAV to the cent.",
    }
    if snap:
        report["return_semantics"] = return_semantics(session, date.fromisoformat(snap), src.id)
    issue_rows = session.execute(
        select(DataQualityIssue.rule, DataQualityIssue.severity, func.count()).where(DataQualityIssue.rule.like("N%"))
        .group_by(DataQualityIssue.rule, DataQualityIssue.severity)
    ).all()
    report["nav_quality"] = {f"{r}:{sev}": n for r, sev, n in issue_rows}
    from app.services.nav_checks import agreement_path

    if agreement_path().exists():
        report["source_agreement"] = json.loads(agreement_path().read_text())
    report["unmatched_amcs"] = summ.get("unmatched_amcs", [])
    return report


def write_report(session: Session) -> dict[str, Any]:
    rep = build_report(session)
    p = report_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rep, indent=2, default=str))
    return rep
