"""Glue between the database / NAV store and the quant engine. No metric logic lives here."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd
from quant_engine import analysis, benchmark
from quant_engine.common import clean_nav, returns
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import FundCategory, Scheme, SchemeMapping
from app.services.nav_load import nav_store

log = logging.getLogger(__name__)
ACCEPTED = ("confirmed", "probable")  # name-only / ambiguous mappings are not used for analytics
MIN_PEERS = 5
RF_CATEGORIES = ("Overnight", "Liquid")
RF_LABEL = "Median daily return of overnight and liquid funds (Growth, confirmed mappings); a proxy, not an official rate"


def store_version() -> float:
    root = Path(get_settings().data_dir) / "silver" / "nav"
    return max((p.stat().st_mtime for p in root.glob("year=*/nav.parquet")), default=0.0)


@dataclass
class FundData:
    scheme_id: int
    name: str
    category: str
    plan_type: str
    option_type: str
    amfi_code: str | None
    mapping_status: str | None
    nav: pd.Series | None
    reason: str | None  # why analytics are unavailable


def _series(code: str) -> pd.Series:
    s = nav_store().read_frames([code]).get(code)
    return clean_nav(s) if s is not None and len(s) else pd.Series(dtype=float)


def load_fund(session: Session, scheme_id: int) -> FundData | None:
    row = session.execute(
        select(Scheme.id, Scheme.name, FundCategory.name, Scheme.plan_type, Scheme.option_type, Scheme.is_insurer_fund,
               SchemeMapping.amfi_code, SchemeMapping.status)
        .join(FundCategory, FundCategory.id == Scheme.category_id)
        .outerjoin(SchemeMapping, SchemeMapping.scheme_id == Scheme.id)
        .where(Scheme.id == scheme_id)
    ).first()
    if row is None:
        return None
    sid, name, cat, plan, opt, insurer, code, status = row
    fd = FundData(sid, name, cat, plan, opt, code, status, None, None)
    if insurer:
        fd.reason = "Insurer-linked fund: no official NAV record"
    elif status not in ACCEPTED:
        fd.reason = ("No confirmed link to an official scheme record" if status in (None, "unmapped", "not_amfi_scheme")
                     else f"Link to the official record is {status}, not used for analytics")
    elif opt != "Growth":
        fd.reason = "Only Growth options are supported: IDCW NAVs exclude distributions, so NAV returns understate total return"
    else:
        s = _series(code)
        if s.empty:
            fd.reason = "No NAV history loaded for this scheme"
        else:
            fd.nav = s
    return fd


def peer_codes(session: Session, fd: FundData) -> list[str]:
    q = (
        select(SchemeMapping.amfi_code)
        .join(Scheme, Scheme.id == SchemeMapping.scheme_id)
        .join(FundCategory, FundCategory.id == Scheme.category_id)
        .where(FundCategory.name == fd.category, Scheme.plan_type == fd.plan_type, Scheme.option_type == "Growth",
               Scheme.is_insurer_fund.is_(False), SchemeMapping.status.in_(ACCEPTED), SchemeMapping.amfi_code != fd.amfi_code)
    )
    return sorted({c for c in session.scalars(q) if c})


def _rf_file() -> Path:
    return Path(get_settings().data_dir) / "gold" / "rf_proxy.parquet"


@lru_cache(maxsize=4)
def _rf_cached(version: float, codes: tuple[str, ...]) -> pd.Series:
    """The risk-free proxy is one small series, so it is computed once from ~60 overnight/liquid funds and saved next to the data.
    A hosted API with little memory then reads a few KB instead of loading those funds."""
    f = _rf_file()
    if f.exists() and f.stat().st_mtime >= version:
        s = pd.read_parquet(f)["rf_proxy"]
        s.index = pd.DatetimeIndex(s.index)
        return s
    navs = load_series(list(codes))
    rf, _ = benchmark.risk_free_proxy(navs)
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        rf.rename("rf_proxy").to_frame().to_parquet(f)
    except OSError:
        pass  # read-only deployment: just recompute next time
    return rf


def risk_free(session: Session) -> pd.Series:
    codes = tuple(sorted({
        c for c in session.scalars(
            select(SchemeMapping.amfi_code).join(Scheme, Scheme.id == SchemeMapping.scheme_id)
            .join(FundCategory, FundCategory.id == Scheme.category_id)
            .where(FundCategory.name.in_(RF_CATEGORIES), Scheme.option_type == "Growth", SchemeMapping.status == "confirmed")
        ) if c
    }))
    return _rf_cached(store_version(), codes) if codes else pd.Series(dtype=float)


@lru_cache(maxsize=256)
def _bench_cached(version: float, own: str, peers: tuple[str, ...]) -> tuple[pd.Series, int]:
    navs = {c: _series(c) for c in peers}
    return benchmark.category_index({k: v for k, v in navs.items() if not v.empty}, MIN_PEERS, exclude=own)


def _bench_files() -> tuple[Path, Path]:
    g = Path(get_settings().data_dir) / "gold"
    return g / "category_benchmarks.parquet", g / "category_benchmarks.json"


def _group_key(category: str, plan: str) -> str:
    return f"{category}|{plan}"


def build_benchmarks(session: Session) -> int:
    """Precompute per-(category, plan) return sums and counts, one category at a time. Run after NAV data or mappings change.
    Lets the API compute any fund's benchmark without loading its peers (a big category means 100+ NAV series)."""
    q = (
        select(FundCategory.name, Scheme.plan_type, SchemeMapping.amfi_code)
        .join(Scheme, Scheme.id == SchemeMapping.scheme_id).join(FundCategory, FundCategory.id == Scheme.category_id)
        .where(Scheme.option_type == "Growth", Scheme.is_insurer_fund.is_(False), SchemeMapping.status.in_(ACCEPTED), SchemeMapping.amfi_code.is_not(None))
    )
    groups: dict[str, set[str]] = {}
    for cat, plan, code in session.execute(q):
        groups.setdefault(_group_key(cat, plan), set()).add(code)
    frames, members = [], {}
    for key, codes in groups.items():
        if len(codes) < MIN_PEERS:
            continue
        total, count, used = benchmark.category_aggregate(load_series(sorted(codes)))
        if not used:
            continue
        members[key] = used
        frames.append(pd.DataFrame({"group": key, "date": total.index, "total": total.to_numpy(), "count": count.to_numpy()}))
    parquet, meta = _bench_files()
    parquet.parent.mkdir(parents=True, exist_ok=True)
    pd.concat(frames, ignore_index=True).to_parquet(parquet, index=False) if frames else None
    meta.write_text(json.dumps(members))
    return len(members)


@lru_cache(maxsize=2)
def _bench_members(mtime: float) -> dict[str, list[str]]:
    return json.loads(_bench_files()[1].read_text())


def _aggregate_for(key: str) -> tuple[pd.Series, pd.Series, list[str]] | None:
    parquet, meta = _bench_files()
    if not (parquet.exists() and meta.exists()) or parquet.stat().st_mtime < store_version():
        return None  # missing or older than the NAV data: fall back to loading peers
    members = _bench_members(meta.stat().st_mtime).get(key)
    if members is None:
        return None
    df = pd.read_parquet(parquet, filters=[("group", "==", key)])
    idx = pd.DatetimeIndex(df["date"])
    return pd.Series(df["total"].to_numpy(), index=idx), pd.Series(df["count"].to_numpy(), index=idx), members


def category_benchmark(session: Session, fd: FundData) -> tuple[pd.Series, int, str]:
    agg = _aggregate_for(_group_key(fd.category, fd.plan_type))
    if agg is not None and fd.nav is not None:
        idx, n = benchmark.category_index_from_aggregate(*agg, MIN_PEERS, own_code=fd.amfi_code, own_nav=fd.nav)
    else:
        peers = tuple(peer_codes(session, fd))
        idx, n = _bench_cached(store_version(), fd.amfi_code or "", peers)
    label = (f"Category average: {n} {fd.plan_type} Growth peers in {fd.category}, equal-weighted, today's surviving funds only"
             if not idx.empty else f"Category average unavailable: fewer than {MIN_PEERS} comparable peers in {fd.category}")
    return idx, n, label


def nav_chart(nav: pd.Series, years: float | None) -> dict:
    sl = nav if years is None else nav.loc[nav.index >= nav.index[-1] - pd.Timedelta(days=round(years * 365.25))]
    dma50, dma200 = nav.rolling(50).mean().reindex(sl.index), nav.rolling(200).mean().reindex(sl.index)
    return {
        "nav": analysis.series_payload(analysis.downsample(sl), 4),
        "dma_50": analysis.series_payload(analysis.downsample(dma50.dropna()), 4),
        "dma_200": analysis.series_payload(analysis.downsample(dma200.dropna()), 4),
    }


def fund_analytics(session: Session, scheme_id: int, years: float | None = 3) -> dict | None:
    fd = load_fund(session, scheme_id)
    if fd is None:
        return None
    base = {"scheme_id": fd.scheme_id, "name": fd.name, "category": fd.category, "plan_type": fd.plan_type,
            "option_type": fd.option_type, "amfi_code": fd.amfi_code, "mapping_status": fd.mapping_status}
    if fd.nav is None:
        return {**base, "available": False, "reason": fd.reason}
    bench, n_peers, b_label = category_benchmark(session, fd)
    rf = risk_free(session)
    rf_arg = rf if not rf.empty else None
    a = analysis.analyse(fd.nav, bench if not bench.empty else None, rf_arg,
                         rf_label=RF_LABEL if rf_arg is not None else "none (0%)", benchmark_label=b_label)
    charts = analysis.chart_series(fd.nav, bench if not bench.empty else None, years)
    charts["nav_chart"] = nav_chart(fd.nav, years)
    return {**base, **a, "benchmark_label": b_label, "peer_count": n_peers, "risk_free_label": RF_LABEL if rf_arg is not None else None,
            "charts": charts, "chart_years": years}


def compare_analytics(session: Session, ids: list[int], years: float | None = 3) -> dict:
    funds, series = [], {}
    for sid in ids:
        fd = load_fund(session, sid)
        if fd is None:
            continue
        funds.append(fd)
        if fd.nav is not None:
            series[sid] = fd.nav
    out_funds = []
    for fd in funds:
        a = fund_analytics(session, fd.scheme_id, years)
        if a is not None:
            a.pop("charts", None)
            out_funds.append(a)
    # common window for overlaid charts
    chart: dict = {"available": False}
    corr: dict = {"ids": [], "matrix": []}
    if len(series) >= 1:
        end = min(s.index[-1] for s in series.values())
        start_floor = max(s.index[0] for s in series.values())
        start = max(start_floor, end - pd.Timedelta(days=round(years * 365.25))) if years else start_floor
        cum, dd, vol = {}, {}, {}
        for sid, s in series.items():
            sl = s.loc[start:end]
            if len(sl) < 30:
                continue
            cum[sid] = analysis.series_payload(analysis.downsample(sl / sl.iloc[0] * 100))
            dd[sid] = analysis.series_payload(analysis.downsample((sl / sl.cummax() - 1) * 100))
            rv = (returns(s).rolling(252, min_periods=252).std(ddof=1) * (252 ** 0.5) * 100).dropna()
            rv = rv.loc[start:end]
            vol[sid] = analysis.series_payload(analysis.downsample(rv), 2)
        if cum:
            chart = {"available": True, "start": start.date().isoformat(), "end": end.date().isoformat(), "cumulative": cum,
                     "drawdown": dd, "rolling_volatility_1y": vol}
        if len(series) >= 2:
            panel = pd.DataFrame({sid: returns(s.loc[start:end]) for sid, s in series.items()}).dropna()
            if len(panel) >= 60:
                c = panel.corr()
                corr = {"ids": [int(i) for i in c.columns], "matrix": [[round(float(v), 3) for v in row] for row in c.to_numpy()],
                        "observations": len(panel)}
    return {"funds": out_funds, "chart": chart, "correlation": corr, "years": years}


def load_series(codes: list[str]) -> dict[str, pd.Series]:
    """One batched store read for many schemes (a per-scheme read costs ~0.3 s each)."""
    return {c: clean_nav(s) for c, s in nav_store().read_frames(codes).items() if len(s)}
