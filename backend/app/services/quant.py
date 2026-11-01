"""Phase 5 orchestration: universe, panel, score history, research outputs, backtests. Metric logic lives in quant_engine."""
from __future__ import annotations

import json
import logging
import threading
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from quant_engine import backtest as bt
from quant_engine import clustering, regime, research, scoring
from quant_engine.panel import build_panel, daily_returns, month_ends
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import session_factory
from app.models import BacktestRun, FundCategory, FundScore, Scheme, SchemeMapping
from app.services.analytics import ACCEPTED, load_series, risk_free, store_version

log = logging.getLogger(__name__)


def quant_dir() -> Path:
    p = Path(get_settings().data_dir) / "gold" / "quant"
    p.mkdir(parents=True, exist_ok=True)
    return p


def history_path() -> Path:
    return quant_dir() / "score_history.parquet"


def universe(session: Session) -> pd.DataFrame:
    rows = session.execute(
        select(SchemeMapping.amfi_code, Scheme.id, Scheme.name, FundCategory.name, Scheme.plan_type, Scheme.asset_tier, Scheme.family_id)
        .join(Scheme, Scheme.id == SchemeMapping.scheme_id).join(FundCategory, FundCategory.id == Scheme.category_id)
        .where(SchemeMapping.status.in_(ACCEPTED), Scheme.option_type == "Growth", Scheme.is_insurer_fund.is_(False))
    ).all()
    df = pd.DataFrame(rows, columns=["code", "scheme_id", "name", "category", "plan", "tier", "family_id"]).dropna(subset=["code"])
    df = df.drop_duplicates("code").set_index("code")
    df["group"] = df["category"] + " | " + df["plan"]
    return df


class Bundle:
    def __init__(self, panel, rets, uni, dropped, rf):
        self.panel, self.rets, self.uni, self.dropped, self.rf = panel, rets, uni, dropped, rf
        self.groups = uni["group"].reindex(panel.columns).dropna()


_bundle_cache: dict[float, Bundle] = {}


def bundle(session: Session) -> Bundle:
    """NAV panel for the whole universe, cached per NAV-store version (building it takes ~10 s)."""
    v = store_version()
    if v in _bundle_cache:
        return _bundle_cache[v]
    uni = universe(session)
    navs = load_series(list(uni.index))
    panel, dropped = build_panel(navs)
    uni = uni.loc[uni.index.intersection(panel.columns)]
    b = Bundle(panel, daily_returns(panel), uni, dropped, risk_free(session))
    _bundle_cache.clear()
    _bundle_cache[v] = b
    return b


# ------------------------------------------------------------------ build (CLI)
def build_all(session: Session, step: int = 1) -> dict[str, Any]:
    b = bundle(session)
    rets, groups = b.rets, b.groups
    first = rets.index[0] + pd.DateOffset(years=3, months=1)
    dates = month_ends(rets.index, first, rets.index[-1], step)
    log.info("scoring history", extra={"dates": len(dates), "funds": rets.shape[1]})
    from app.services import lite

    lite.write_light_artifacts(b)
    hist = research.score_history(rets, b.rf if not b.rf.empty else None, groups, dates)
    long = pd.concat({d: df for d, df in hist.items()}, names=["date", "code"]).reset_index()
    long.to_parquet(history_path(), index=False)

    latest = hist[dates[-1]]
    _store_scores(session, latest, dates[-1], b)
    out = _research(hist, b, latest)
    return {"dates": len(dates), "first": str(dates[0].date()), "last": str(dates[-1].date()), "funds": int(rets.shape[1]),
            "dropped_suspect_nav": len(b.dropped), "scored_latest": int(latest["composite"].notna().sum()), **out}


def _store_scores(session: Session, latest: pd.DataFrame, asof: pd.Timestamp, b: Bundle) -> None:
    session.execute(delete(FundScore))
    metric_keys = scoring.METRIC_KEYS + scoring.EXTRA_KEYS
    for code, row in latest.iterrows():
        if code not in b.uni.index or pd.isna(row.get("group")):
            continue
        clean = lambda v: None if v is None or (isinstance(v, float) and np.isnan(v)) else float(v)
        detail = {
            "metrics": {k: clean(row.get(k)) for k in metric_keys},
            "percentiles": {k: clean(row.get(f"p_{k}")) for k in scoring.METRIC_KEYS},
            "z": {k: clean(row.get(f"z_{k}")) for k in scoring.METRIC_KEYS},
            "factors": {f: clean(row.get(f"f_{f}")) for f in scoring.FACTORS},
            "contributions": {f: clean(row.get(f"c_{f}")) for f in scoring.FACTORS},
        }
        session.add(FundScore(
            scheme_id=int(b.uni.at[code, "scheme_id"]), as_of=asof.to_pydatetime(), methodology_version=scoring.SCORE_VERSION,
            peer_group=row["group"], peers=int(row["peers"]), composite=clean(row.get("composite")), coverage=clean(row.get("coverage")),
            rank_in_group=int(row["rank"]) if not pd.isna(row.get("rank")) else None, detail=detail,
        ))
    session.commit()


def _research(hist: dict, b: Bundle, latest: pd.DataFrame) -> dict[str, Any]:
    names = b.uni["name"].to_dict()
    asof = max(hist)
    f_keys = [f"f_{f}" for f in scoring.FACTORS if f != "stability"] + ["composite"]
    factors = {
        "generated_at": datetime.now(UTC).isoformat(), "scoring_version": scoring.SCORE_VERSION,
        "first_date": str(min(hist).date()), "last_date": str(asof.date()), "dates": len(hist),
        "ic": research.factor_ic(hist, b.panel, b.groups),
        "persistence": research.persistence(hist, b.panel, b.groups, 12),
        "caveats": [
            "Survivorship bias: only funds that exist today; closed or merged funds are missing, which flatters persistence.",
            "Peer groups use today's classification at every historical date.",
            "t-statistics use non-overlapping dates; overlapping forward windows are autocorrelated.",
            "Many signals and horizons are tested together, so some will look significant by chance.",
            "Weights in the composite are research hypotheses and have not been tuned on this data.",
        ],
    }
    stats = {
        "correlations": research.factor_correlations(hist, f_keys),
        "distributions": research.distribution_summary(latest, ["ret_1y", "ret_3y", "vol_3y", "sharpe_3y", "max_dd_3y", "mom_12m", "composite"]),
        "metric_correlations": research.factor_correlations(hist, [f"p_{k}" for k in scoring.METRIC_KEYS]),
        "score_by_tier": _score_by_tier(latest, b),
    }
    (quant_dir() / "factors.json").write_text(json.dumps({"factors": factors, "statistics": stats}, default=_j))

    clusters = {}
    tiers = b.uni["tier"].reindex(latest.index)
    for tier in ["Equity", "Debt", "Hybrid", "Other"]:
        sub = latest[(tiers == tier) & (b.uni["plan"].reindex(latest.index) == "Direct")]
        res = clustering.cluster_tier(sub)
        if res.get("available"):
            res["names"] = {c: names.get(c, c) for c in sub.index}
        clusters[tier] = res
    (quant_dir() / "clusters.json").write_text(json.dumps({"clusters": clusters, "note": "Direct-plan Growth schemes only, one clustering per asset tier."}, default=_j))

    eq = b.uni[(b.uni["tier"] == "Equity") & (b.uni["plan"] == "Direct")].index
    idx = regime.market_index(b.rets, list(eq))
    reg = _regimes(idx)
    (quant_dir() / "regimes.json").write_text(json.dumps(reg, default=_j))
    return {"ic_rows": len(factors["ic"]), "clusters_tiers": [t for t, r in clusters.items() if r.get("available")], "regime_days": len(idx)}


def _score_by_tier(latest: pd.DataFrame, b: Bundle) -> list[dict]:
    t = b.uni["tier"].reindex(latest.index)
    out = []
    for tier, sub in latest.groupby(t):
        c = sub["composite"].dropna()
        if len(c) >= 5:
            out.append({"tier": tier, "scored": len(c), "mean": float(c.mean()), "p10": float(c.quantile(.1)), "median": float(c.median()), "p90": float(c.quantile(.9))})
    return out


def _regimes(idx: pd.Series) -> dict[str, Any]:
    trend, vol = regime.trend_regime(idx), regime.vol_regime(idx)
    hmm = regime.hmm_regimes(idx, 3)
    step = max(1, len(idx) // 700)
    out: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(), "proxy": "Equal-weighted average of Direct-plan equity Growth funds that exist today (survivors only)",
        "start": str(idx.index[0].date()), "end": str(idx.index[-1].date()),
        "index": [[d.date().isoformat(), round(float(v), 2)] for d, v in idx.iloc[::step].items()],
        "current": {"trend": _last(trend), "volatility": _last(vol), "hmm": _last(hmm["labels"]) if hmm.get("available") else None},
        "trend": {"stats": regime.regime_stats(idx, trend), "transitions": regime.transition_matrix(trend),
                  "timeline": _timeline(trend), "rule": "bull: above the 200-day average with positive 6-month momentum; bear: below with negative; otherwise sideways. Uses only past data."},
        "volatility": {"stats": regime.regime_stats(idx, vol.where(vol.notna(), None)), "timeline": _timeline(vol),
                       "rule": "Rolling 63-day volatility vs the 33rd/67th percentiles of its own past (expanding window, needs 2 years)."},
    }
    if hmm.get("available"):
        lab = hmm["labels"]
        out["hmm"] = {"stats": regime.regime_stats(idx, lab), "transitions": regime.transition_matrix(lab), "timeline": _timeline(lab),
                      "state_params": hmm["state_params"], "train_end": str(hmm["train_end"].date()), "note": hmm["note"],
                      "current_probabilities": {k: float(v) for k, v in hmm["probabilities"].iloc[-1].items()}}
    else:
        out["hmm"] = {"available": False, "reason": hmm.get("reason")}
    gmm = regime.gmm_regimes(idx)
    out["gmm"] = {"stats": regime.regime_stats(idx, gmm), "hindsight": True,
                  "note": "Fitted on the full sample: descriptive only, never used for point-in-time decisions."}
    return out


def _last(s: pd.Series):
    s = s.dropna()
    return None if s.empty else str(s.iloc[-1])


def _timeline(lab: pd.Series) -> list[dict]:
    lab = lab.dropna()
    if lab.empty:
        return []
    runs = (lab != lab.shift()).cumsum()
    out = []
    for _, seg in lab.groupby(runs):
        out.append({"regime": str(seg.iloc[0]), "start": seg.index[0].date().isoformat(), "end": seg.index[-1].date().isoformat()})
    return out


def _j(o):
    if isinstance(o, (np.floating,)):
        return None if np.isnan(o) else float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (pd.Timestamp,)):
        return o.isoformat()
    raise TypeError(type(o))


def read_json(name: str) -> dict | None:
    p = quant_dir() / name
    return json.loads(p.read_text()) if p.exists() else None


# ------------------------------------------------------------------ backtests
@lru_cache(maxsize=2)
def _history_cached(mtime: float) -> dict[pd.Timestamp, pd.DataFrame]:
    long = pd.read_parquet(history_path())
    return {pd.Timestamp(d): g.drop(columns="date").set_index("code") for d, g in long.groupby("date")}


def history() -> dict[pd.Timestamp, pd.DataFrame]:
    p = history_path()
    if not p.exists():
        raise FileNotFoundError("score history not built; run `python -m app.cli.pipeline quant`")
    return _history_cached(p.stat().st_mtime)


LIMITS = {"top_n": (3, 30), "rebalance_months": (1, 12), "cost_pct": (0.0, 2.0), "exit_load_pct": (0.0, 3.0), "delay_days": (0, 10)}


def validate_request(req: dict) -> tuple[bt.BacktestConfig, dict]:
    if req.get("strategy") not in bt.STRATEGIES:
        raise ValueError(f"strategy must be one of {sorted(bt.STRATEGIES)}")
    for k, (lo, hi) in LIMITS.items():
        if k in req and not lo <= float(req[k]) <= hi:
            raise ValueError(f"{k} must be between {lo} and {hi}")
    uni = req.get("universe") or {}
    if uni.get("tier") not in (None, "Equity", "Debt", "Hybrid", "Other"):
        raise ValueError("universe.tier must be Equity, Debt, Hybrid or Other")
    if uni.get("plan", "Direct") not in ("Direct", "Regular", "Unspecified"):
        raise ValueError("universe.plan must be Direct, Regular or Unspecified")
    fields = {k: req[k] for k in ("strategy", "top_n", "rebalance_months", "start", "end", "cost_pct", "exit_load_pct", "delay_days", "oos_start") if k in req}
    for k in ("start", "end", "oos_start"):
        if fields.get(k):
            pd.Timestamp(fields[k])  # raises on garbage
    cfg = bt.BacktestConfig(**fields)
    return cfg, {"tier": uni.get("tier"), "category": uni.get("category"), "plan": uni.get("plan", "Direct")}


def universe_codes(b: Bundle, u: dict, tier_override: str | None = None) -> set[str]:
    df = b.uni
    df = df[df["plan"] == u["plan"]]
    tier = tier_override or u.get("tier")
    if tier:
        df = df[df["tier"] == tier]
    if u.get("category") and not tier_override:
        df = df[df["category"] == u["category"]]
    return set(df.index)


def execute(run_id: int) -> None:
    """Run one backtest and store the result. Called from a worker thread with its own DB session."""
    with session_factory()() as s:
        run = s.get(BacktestRun, run_id)
        run.status = "running"
        s.commit()
        try:
            cfg, u = validate_request(run.request)
            b = bundle(s)
            hist = history()
            codes = universe_codes(b, u)
            if len(codes) < 10:
                raise ValueError(f"only {len(codes)} funds match this universe; at least 10 are needed")
            risk_on = defensive = None
            if cfg.strategy == "regime_aware":
                eq = b.uni[(b.uni["tier"] == "Equity") & (b.uni["plan"] == "Direct")].index
                risk_on = regime.risk_on(regime.market_index(b.rets, list(eq)))
                defensive = universe_codes(b, {**u, "category": None}, tier_override="Debt")
            res = bt.run_backtest(b.panel, hist, codes, cfg, b.rf if not b.rf.empty else None, risk_on, defensive)
            res["universe"] = {**u, "funds": len(codes)}
            res["data_version"] = {"scoring": scoring.SCORE_VERSION, "nav_store": store_version(), "history_dates": len(hist)}
            run.result, run.status = json.loads(json.dumps(res, default=_j)), "succeeded"
        except Exception as exc:
            log.exception("backtest failed", extra={"run_id": run_id})
            run.status, run.error = "failed", str(exc)[:900]
        run.finished_at = datetime.now(UTC)
        s.commit()


class BacktestsDisabled(RuntimeError):
    pass


def submit(session: Session, req: dict) -> BacktestRun:
    cfg, u = validate_request(req)
    h = history_path()
    key = cfg.hash(json.dumps(u, sort_keys=True) + str(h.stat().st_mtime if h.exists() else 0) + str(store_version()))
    existing = session.scalars(select(BacktestRun).where(BacktestRun.config_hash == key, BacktestRun.status.in_(("succeeded", "running", "queued")))
                               .order_by(BacktestRun.id.desc())).first()
    if existing is not None:
        return existing
    if not get_settings().enable_backtests:
        raise BacktestsDisabled("Running new backtests is switched off on this server because it needs about 1 GB of memory. "
                                "Run them locally (see the README); previously computed results are still available.")
    run = BacktestRun(config_hash=key, request=req, status="queued")
    session.add(run)
    session.commit()
    threading.Thread(target=execute, args=(run.id,), daemon=True).start()
    return run
