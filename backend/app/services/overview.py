"""Market overview aggregates from the latest snapshot.

Universe (default): non-quarantined, non-insurer, non-discontinued schemes. Insurer/ULIP funds are not AMFI
mutual funds; they stay in the database and are reported separately in `counts`.
AUM is aggregated per fund family (max over share classes) because Net Assets repeat across classes.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import Float, case, cast, func, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session

from app.models import AMC, FundCategory, FundSnapshot, Scheme

HORIZONS = {
    "ytd": ("ytd_return", "ytd_return_cat_pct"),
    "3m": ("return_3m", "3mo_return_cat_pct"),
    "1y": ("return_1y", "1year_return_cat_pct"),
    "3y": ("return_3y", "3year_return_cat_pct"),
    "5y": ("return_5y", "5year_return_cat_pct"),
}
MIN_CATEGORY_N = 5
MIN_AMC_N = 10


def _feature(key: str):
    return cast(FundSnapshot.features.op("->>")(key), Float)


def _median(col):
    return func.percentile_cont(0.5).within_group(col)


def _universe_filter(run_id: int, include_insurer: bool):
    conds = [FundSnapshot.ingestion_run_id == run_id, FundSnapshot.quarantined.is_(False), Scheme.is_discontinued.is_(False)]
    if not include_insurer:
        conds.append(Scheme.is_insurer_fund.is_(False))
    return conds


def overview(session: Session, run_id: int, *, include_insurer: bool = False, top_horizon: str = "1y") -> dict[str, Any]:
    if top_horizon not in HORIZONS:
        raise ValueError(f"horizon must be one of {sorted(HORIZONS)}")
    uni = _universe_filter(run_id, include_insurer)

    def scalar(stmt):
        return session.scalar(stmt)

    # ---- counts
    total = scalar(select(func.count()).select_from(FundSnapshot).where(FundSnapshot.ingestion_run_id == run_id))
    counts = {
        "schemes_total": total,
        "schemes_in_universe": scalar(
            select(func.count()).select_from(Scheme).join(FundSnapshot, FundSnapshot.scheme_id == Scheme.id).where(*uni)
        ),
        "insurer_funds": scalar(
            select(func.count()).select_from(Scheme).join(FundSnapshot, FundSnapshot.scheme_id == Scheme.id)
            .where(FundSnapshot.ingestion_run_id == run_id, Scheme.is_insurer_fund.is_(True))
        ),
        "discontinued": scalar(
            select(func.count()).select_from(Scheme).join(FundSnapshot, FundSnapshot.scheme_id == Scheme.id)
            .where(FundSnapshot.ingestion_run_id == run_id, Scheme.is_discontinued.is_(True))
        ),
        "quarantined": scalar(
            select(func.count()).select_from(FundSnapshot)
            .where(FundSnapshot.ingestion_run_id == run_id, FundSnapshot.quarantined.is_(True))
        ),
        "families": scalar(
            select(func.count(func.distinct(Scheme.family_id))).select_from(Scheme)
            .join(FundSnapshot, FundSnapshot.scheme_id == Scheme.id).where(*uni)
        ),
        "amcs": scalar(
            select(func.count(func.distinct(Scheme.amc_id))).select_from(Scheme)
            .join(FundSnapshot, FundSnapshot.scheme_id == Scheme.id).where(*uni)
        ),
        "categories": scalar(
            select(func.count(func.distinct(Scheme.category_id))).select_from(Scheme)
            .join(FundSnapshot, FundSnapshot.scheme_id == Scheme.id).where(*uni)
        ),
    }

    # ---- tier distribution
    tiers = [
        {"tier": t, "schemes": n}
        for t, n in session.execute(
            select(Scheme.asset_tier, func.count()).join(FundSnapshot, FundSnapshot.scheme_id == Scheme.id)
            .where(*uni).group_by(Scheme.asset_tier).order_by(func.count().desc())
        )
    ]

    # ---- category table (medians per horizon)
    med_cols = [_median(getattr(FundSnapshot, col)).label(h) for h, (col, _) in HORIZONS.items()]
    cat_rows = session.execute(
        select(FundCategory.name, Scheme.asset_tier, func.count().label("n"), *med_cols)
        .select_from(Scheme).join(FundSnapshot, FundSnapshot.scheme_id == Scheme.id)
        .join(FundCategory, FundCategory.id == Scheme.category_id).where(*uni)
        .group_by(FundCategory.name, Scheme.asset_tier)
    ).all()
    categories = sorted(
        [
            {"category": r.name, "asset_tier": r.asset_tier, "schemes": r.n, "low_sample": r.n < MIN_CATEGORY_N,
             "median_returns": {h: getattr(r, h) for h in HORIZONS}}
            for r in cat_rows
        ],
        key=lambda c: -(c["median_returns"]["1y"] if c["median_returns"]["1y"] is not None else -1e9),
    )

    # ---- breadth (absolute, not category-relative: category percentiles are ~50% by construction)
    def share(cond, notnull):
        return func.avg(case((cond, 1.0), else_=0.0)).filter(notnull)

    breadth_rows = session.execute(
        select(
            Scheme.asset_tier,
            *[share(getattr(FundSnapshot, c) > 0, getattr(FundSnapshot, c).is_not(None)).label(f"pos_{h}")
              for h, (c, _) in HORIZONS.items()],
            *[func.count(getattr(FundSnapshot, c)).label(f"n_{h}") for h, (c, _) in HORIZONS.items()],
            share(FundSnapshot.price > FundSnapshot.avg_50d, FundSnapshot.avg_50d.is_not(None)).label("above_50d"),
            share(FundSnapshot.price > FundSnapshot.avg_200d, FundSnapshot.avg_200d.is_not(None)).label("above_200d"),
            func.count().label("n"),
        )
        .select_from(Scheme).join(FundSnapshot, FundSnapshot.scheme_id == Scheme.id).where(*uni)
        .group_by(Scheme.asset_tier)
    ).all()
    breadth = [
        {
            "tier": r.asset_tier, "schemes": r.n,
            "positive_return_share": {h: getattr(r, f"pos_{h}") for h in HORIZONS},
            "observations": {h: getattr(r, f"n_{h}") for h in HORIZONS},
            "above_50d_avg": r.above_50d, "above_200d_avg": r.above_200d,
        }
        for r in breadth_rows
    ]

    # ---- AMC leaderboard: median 3Y category percentile, min sample
    pct3 = _feature("3year_return_cat_pct")
    amc_rows = session.execute(
        select(AMC.name, func.count(pct3).label("n"), (_median(pct3) * 100).label("median_pct"),
               func.count(func.distinct(Scheme.family_id)).label("families"),
               func.count(func.distinct(Scheme.category_id)).label("categories"))
        .select_from(Scheme).join(FundSnapshot, FundSnapshot.scheme_id == Scheme.id).join(AMC, AMC.id == Scheme.amc_id)
        .where(*uni).group_by(AMC.name).having(func.count(pct3) >= MIN_AMC_N)
        .order_by((_median(pct3)).desc())
    ).all()
    amcs = [
        {"amc": r.name, "schemes_with_3y": r.n, "median_3y_category_percentile": r.median_pct,
         "families": r.families, "categories": r.categories}
        for r in amc_rows
    ]
    amc_total = scalar(select(func.count(func.distinct(Scheme.amc_id))).select_from(Scheme)
                       .join(FundSnapshot, FundSnapshot.scheme_id == Scheme.id).where(*uni))

    # ---- one row per family: top performers and top AUM
    ret_col = getattr(FundSnapshot, HORIZONS[top_horizon][0])
    top = session.execute(
        select(Scheme.id, Scheme.name, AMC.name.label("amc"), FundCategory.name.label("category"), ret_col.label("ret"),
               FundSnapshot.net_assets)
        .select_from(Scheme).join(FundSnapshot, FundSnapshot.scheme_id == Scheme.id)
        .join(AMC, AMC.id == Scheme.amc_id).join(FundCategory, FundCategory.id == Scheme.category_id)
        .where(*uni, ret_col.is_not(None), Scheme.family_id.is_not(None))
        .ext(distinct_on(Scheme.family_id)).order_by(Scheme.family_id, ret_col.desc())
    ).all()
    top_performers = sorted(top, key=lambda r: -r.ret)[:10]

    aum_pick = session.execute(
        select(Scheme.id, Scheme.name, AMC.name.label("amc"), FundCategory.name.label("category"),
               FundSnapshot.net_assets, FundSnapshot.return_1y)
        .select_from(Scheme).join(FundSnapshot, FundSnapshot.scheme_id == Scheme.id)
        .join(AMC, AMC.id == Scheme.amc_id).join(FundCategory, FundCategory.id == Scheme.category_id)
        .where(*uni, FundSnapshot.net_assets.is_not(None), Scheme.family_id.is_not(None))
        .ext(distinct_on(Scheme.family_id)).order_by(Scheme.family_id, FundSnapshot.net_assets.desc())
    ).all()
    aum_total = sum(r.net_assets for r in aum_pick)
    fam_total = counts["families"] or 0
    top_aum = sorted(aum_pick, key=lambda r: -r.net_assets)[:10]

    avg_1y = session.execute(
        select(func.avg(FundSnapshot.return_1y), _median(FundSnapshot.return_1y), func.count(FundSnapshot.return_1y))
        .select_from(Scheme).join(FundSnapshot, FundSnapshot.scheme_id == Scheme.id).where(*uni)
    ).one()

    return {
        "ingestion_run_id": run_id,
        "universe": {
            "description": "non-quarantined, non-discontinued" + ("" if include_insurer else ", non-insurer") + " schemes",
            "include_insurer": include_insurer,
        },
        "counts": counts,
        "tiers": tiers,
        "returns_1y": {"mean": avg_1y[0], "median": avg_1y[1], "n": avg_1y[2]},
        "aum": {
            "total_rupees": aum_total,
            "families_with_aum": len(aum_pick),
            "families_total": fam_total,
            "coverage": (len(aum_pick) / fam_total) if fam_total else None,
            "note": "Sum of one share class per fund family; families without Net Assets are excluded.",
        },
        "categories": categories,
        "breadth": breadth,
        "amc_leaderboard": {
            "min_schemes": MIN_AMC_N, "amcs_ranked": len(amcs), "amcs_in_universe": amc_total, "rows": amcs,
        },
        "top_performers": {
            "horizon": top_horizon,
            "note": "One share class per fund family (highest return); returns are as reported by Yahoo.",
            "rows": [r._asdict() for r in top_performers],
        },
        "top_by_aum": {"rows": [r._asdict() for r in top_aum]},
        "snapshot_note": "Single snapshot of unknown date. No time series, flows or AUM history are available.",
    }
