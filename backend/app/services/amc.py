"""AMC intelligence: category-adjusted comparison of fund houses.

An AMC is never ranked by its single best fund or by raw returns (which reward owning risky categories).
Each fund is placed as a percentile within its own category and plan; an AMC is summarised by the MEDIAN of those
percentiles across its funds, and only when it has enough funds in enough categories. Direct plans only, so share
classes of one portfolio do not count twice. Scores are survivor-only research indicators, not recommendations.
"""
from __future__ import annotations

import statistics
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AMC, FundCategory, FundScore, Scheme, SchemeMetric

AMC_VERSION = "amc-1.0.0"
MIN_FUNDS = 5       # scored funds
MIN_CATEGORIES = 3  # distinct categories


def _pct(rank: int | None, peers: int | None) -> float | None:
    if not rank or not peers or peers < 2:
        return None
    return 100.0 * (1 - (rank - 1) / (peers - 1))


def _med(xs: list[float]) -> float | None:
    return float(statistics.median(xs)) if xs else None


def _rows(session: Session) -> list[dict]:
    q = (select(Scheme.id, Scheme.name, AMC.id, AMC.name, FundCategory.name, FundScore.rank_in_group, FundScore.peers, FundScore.composite,
                SchemeMetric.pctile_ret_3y, SchemeMetric.pctile_sharpe_3y, SchemeMetric.ret_3y)
         .join(AMC, AMC.id == Scheme.amc_id).join(FundCategory, FundCategory.id == Scheme.category_id)
         .outerjoin(FundScore, FundScore.scheme_id == Scheme.id).outerjoin(SchemeMetric, SchemeMetric.scheme_id == Scheme.id)
         .where(Scheme.plan_type == "Direct", Scheme.option_type == "Growth", Scheme.is_insurer_fund.is_(False), AMC.is_insurer.is_(False)))
    keys = ["scheme_id", "name", "amc_id", "amc", "category", "rank", "peers", "composite", "p_ret", "p_sharpe", "ret_3y"]
    out = []
    for r in session.execute(q).all():
        d = dict(zip(keys, r))
        d["p_score"] = _pct(d["rank"], d["peers"])
        out.append(d)
    return out


def summarise(rows: list[dict]) -> list[dict]:
    by: dict[int, list[dict]] = {}
    for r in rows:
        by.setdefault(r["amc_id"], []).append(r)
    out = []
    for amc_id, fs in by.items():
        scored = [f for f in fs if f["p_score"] is not None]
        cats = {f["category"] for f in scored}
        counts: dict[str, int] = {}
        for f in fs:
            counts[f["category"]] = counts.get(f["category"], 0) + 1
        n = len(fs)
        hhi = sum((c / n) ** 2 for c in counts.values())
        eligible = len(scored) >= MIN_FUNDS and len(cats) >= MIN_CATEGORIES
        row = {
            "amc_id": amc_id, "amc": fs[0]["amc"], "funds": n, "scored_funds": len(scored), "categories": len(counts),
            "eligible": eligible,
            "reason": None if eligible else f"needs at least {MIN_FUNDS} scored funds across {MIN_CATEGORIES} categories (has {len(scored)} across {len(cats)})",
            "median_score_percentile": _med([f["p_score"] for f in scored]) if eligible else None,
            "median_return_percentile": _med([f["p_ret"] for f in fs if f["p_ret"] is not None]) if eligible else None,
            "median_sharpe_percentile": _med([f["p_sharpe"] for f in fs if f["p_sharpe"] is not None]) if eligible else None,
            "share_above_median": (100.0 * sum(f["p_score"] > 50 for f in scored) / len(scored)) if eligible else None,
            "share_top_quartile": (100.0 * sum(f["p_score"] >= 75 for f in scored) / len(scored)) if eligible else None,
            "share_bottom_quartile": (100.0 * sum(f["p_score"] < 25 for f in scored) / len(scored)) if eligible else None,
            "concentration_hhi": hhi, "largest_category": max(counts, key=counts.get), "largest_category_share": 100.0 * max(counts.values()) / n,
        }
        out.append(row)
    out.sort(key=lambda r: (r["median_score_percentile"] is None, -(r["median_score_percentile"] or 0), r["amc"]))
    rank = 0
    for r in out:
        if r["eligible"]:
            rank += 1
            r["rank"] = rank
        else:
            r["rank"] = None
    return out


def ranking(session: Session) -> dict[str, Any]:
    rows = summarise(_rows(session))
    return {
        "version": AMC_VERSION, "amcs": rows, "eligible": sum(r["eligible"] for r in rows),
        "method": [
            "Direct Growth plans only, so share classes are not double counted.",
            "Each fund is placed as a percentile (100 = best) among peers in its own category, using the QuantSynthica score.",
            f"An AMC is summarised by the median fund percentile and is ranked only with at least {MIN_FUNDS} scored funds in {MIN_CATEGORIES} categories.",
            "Median, not best fund: one star scheme cannot lift an AMC. A median near 50 means typical peers.",
            "Survivors only: AMCs that closed or merged away poor schemes look better than they were. Scores are research indicators, not advice.",
        ],
    }


def detail(session: Session, amc_id: int) -> dict[str, Any] | None:
    rows = _rows(session)
    summary = next((r for r in summarise(rows) if r["amc_id"] == amc_id), None)
    if summary is None:
        return None
    cats: dict[str, list[dict]] = {}
    for f in rows:
        if f["amc_id"] == amc_id:
            cats.setdefault(f["category"], []).append(f)
    return {
        "version": AMC_VERSION, "summary": summary,
        "categories": sorted(({"category": c, "funds": len(fs), "median_score_percentile": _med([f["p_score"] for f in fs if f["p_score"] is not None]),
                               "best_percentile": max((f["p_score"] for f in fs if f["p_score"] is not None), default=None)} for c, fs in cats.items()),
                             key=lambda x: -x["funds"]),
        "funds": sorted(({k: f[k] for k in ("scheme_id", "name", "category", "composite", "p_score", "ret_3y")} for fs in cats.values() for f in fs),
                        key=lambda x: (x["p_score"] is None, -(x["p_score"] or 0), x["name"])),
        "note": "Funds without a score are listed with a dash; they are excluded from the AMC medians, never counted as zero.",
    }
