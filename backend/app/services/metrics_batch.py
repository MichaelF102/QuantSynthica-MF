"""Compute NAV-derived metrics for every eligible scheme and rank them within peer groups."""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from datetime import datetime

import pandas as pd
from quant_engine import METHODOLOGY_VERSION, analysis, benchmark
from quant_engine import performance as perf
from quant_engine.common import clean_nav
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import FundCategory, Scheme, SchemeMapping, SchemeMetric
from app.services.analytics import ACCEPTED, MIN_PEERS, _series, risk_free

log = logging.getLogger(__name__)
# metric -> True if higher is better
RANKED = {"ret_3y": True, "sharpe_3y": True, "sortino_3y": True, "max_dd_3y": True, "vol_3y": False}


def _val(block: dict | None, key: str):
    m = (block or {}).get(key)
    return m.get("value") if m else None


def compute_all(session: Session) -> dict[str, int]:
    rows = session.execute(
        select(Scheme.id, SchemeMapping.amfi_code, FundCategory.name, Scheme.plan_type)
        .join(SchemeMapping, SchemeMapping.scheme_id == Scheme.id)
        .join(FundCategory, FundCategory.id == Scheme.category_id)
        .where(SchemeMapping.status.in_(ACCEPTED), Scheme.option_type == "Growth", Scheme.is_insurer_fund.is_(False))
    ).all()
    t0 = time.time()
    rf = risk_free(session)
    rf_arg = rf if not rf.empty else None
    groups: dict[tuple[str, str], list[tuple[int, str]]] = defaultdict(list)
    for sid, code, cat, plan in rows:
        groups[(cat, plan)].append((sid, code))

    results: list[dict] = []
    for (cat, plan), members in groups.items():
        navs = {code: clean_nav(_series(code)) for _, code in members}
        navs = {c: s for c, s in navs.items() if len(s) >= 30}
        for sid, code in members:
            nav = navs.get(code)
            if nav is None:
                continue
            end = nav.index[-1]
            bench, n = benchmark.category_index(navs, MIN_PEERS, exclude=code)
            blk = analysis.risk_block(nav, end, 3, bench if not bench.empty else None, rf_arg)
            tr = perf.trailing_returns(nav)
            b = blk.get("benchmark") if blk.get("available") else None
            results.append({
                "scheme_id": sid, "amfi_code": code, "as_of": datetime.combine(end.date(), datetime.min.time()),
                "peer_group": f"{cat} / {plan} / Growth", "peer_count": len(navs),
                "ret_1y": tr["1y"].value, "ret_3y": tr["3y"].value, "ret_5y": tr["5y"].value,
                "vol_3y": _val(blk, "volatility"), "sharpe_3y": _val(blk, "sharpe_ratio"), "sortino_3y": _val(blk, "sortino_ratio"),
                "max_dd_3y": _val(blk, "max_drawdown"), "calmar_3y": _val(blk, "calmar_ratio"),
                "beta_3y": _val(b, "beta"), "alpha_3y": _val(b, "alpha"), "te_3y": _val(b, "tracking_error"), "ir_3y": _val(b, "information_ratio"),
            })

    # peer percentiles (0-100, higher = better), only with enough peers that have the metric
    by_group: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        by_group[r["peer_group"]].append(r)
    for g in by_group.values():
        for metric, higher_better in RANKED.items():
            have = [r for r in g if r[metric] is not None]
            if len(have) < MIN_PEERS:
                for r in g:
                    r["pctile_" + metric] = None
                continue
            s = pd.Series({id(r): r[metric] for r in have})
            pct = s.rank(method="average", ascending=higher_better) - 1
            pct = pct / (len(have) - 1) * 100
            for r in g:
                r["pctile_" + metric] = float(pct[id(r)]) if r[metric] is not None else None

    session.execute(delete(SchemeMetric))
    for r in results:
        session.add(SchemeMetric(methodology_version=METHODOLOGY_VERSION, **r))
    session.commit()
    out = {"schemes": len(results), "groups": len(by_group), "seconds": round(time.time() - t0)}
    log.info("metrics computed", extra=out)
    return out
