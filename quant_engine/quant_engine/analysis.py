"""One call that produces every Phase 4 metric for a fund, plus chart series. Callers (API, notebooks,
batch jobs) use this so all surfaces share a single implementation."""
from __future__ import annotations

import pandas as pd

from quant_engine import METHODOLOGY_VERSION, risk
from quant_engine import performance as perf
from quant_engine.common import (
    Metric,
    clean_nav,
    conventions,
    returns,
    suspect_moves,
    window_slice,
)

WINDOWS = (1, 3, 5)
MAX_POINTS = 600


def _d(m: Metric | None) -> dict | None:
    return m.to_dict() if m is not None else None


def risk_block(nav: pd.Series, end: pd.Timestamp | None, years: float, bench: pd.Series | None, rf: pd.Series | float | None) -> dict:
    sl, why = window_slice(nav, end, years)
    if why or len(sl) < 30:
        return {"years": years, "available": False, "reason": why or "too few observations"}
    bad = [(t, v) for t, v in suspect_moves(sl)]
    if bad:
        t, v = bad[0]
        return {"years": years, "available": False, "data_issue": True,
                "reason": f"NAV moved {v * 100:+.0f}% in one day on {t.date()} (probable unit split or data error); excluded until verified"}
    r = returns(sl)
    dd = risk.max_drawdown(sl)
    out: dict = {
        "years": years, "available": True, "window_start": sl.index[0].date().isoformat(), "window_end": sl.index[-1].date().isoformat(),
        "cagr": _d(perf.cagr(sl)), "volatility": _d(risk.annualised_volatility(r)),
        "downside_deviation": _d(risk.downside_deviation(r, 0.0)),
        "sharpe_ratio": _d(risk.sharpe_ratio(r, rf)), "sortino_ratio": _d(risk.sortino_ratio(r, rf)),
        "max_drawdown": _d(dd["metric"]), "calmar_ratio": _d(risk.calmar_ratio(sl)),
        "var_95": _d(risk.var_historical(r, 0.95)), "cvar_95": _d(risk.cvar_historical(r, 0.95)),
        "var_99": _d(risk.var_historical(r, 0.99)), "cvar_99": _d(risk.cvar_historical(r, 0.99)),
        "var_param_95": _d(risk.var_parametric(r, 0.95)),
        "skewness": _d(risk.skewness(r)), "excess_kurtosis": _d(risk.excess_kurtosis(r)),
        "drawdown_detail": {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in dd.items() if k != "metric"},
    }
    if bench is not None and not bench.empty:
        bsl, bwhy = window_slice(bench, sl.index[-1], years)
        br = returns(bsl) if not bwhy else pd.Series(dtype=float)
        ba = risk.beta_alpha(r, br, rf)
        out["benchmark"] = {
            **{k: _d(v) for k, v in ba.items()},
            "correlation": _d(risk.correlation(r, br)), "tracking_error": _d(perf.tracking_error(r, br)),
            "information_ratio": _d(perf.information_ratio(r, br)),
            **{k: _d(v) for k, v in (perf.capture_ratios(sl, bsl) if not bwhy and len(bsl) > 60 else {}).items()},
            "benchmark_cagr": _d(perf.cagr(bsl)) if not bwhy else None,
        }
    return out


def downsample(s: pd.Series, max_points: int = MAX_POINTS) -> pd.Series:
    if len(s) <= max_points:
        return s
    step = len(s) / max_points
    idx = sorted({int(i * step) for i in range(max_points)} | {len(s) - 1})
    return s.iloc[idx]


def series_payload(s: pd.Series, digits: int = 3) -> list[list]:
    return [[t.date().isoformat(), round(float(v), digits)] for t, v in s.items()]


def chart_series(nav: pd.Series, bench: pd.Series | None, years: float | None) -> dict:
    """Rebased cumulative, drawdown, rolling returns and rolling volatility, downsampled for the browser."""
    sl, why = window_slice(nav, None, years)
    if why or len(sl) < 2:
        return {"available": False, "reason": why or "too few observations"}
    cum = sl / sl.iloc[0] * 100
    out: dict = {"available": True, "cumulative": {"fund": series_payload(downsample(cum))}, "drawdown": {"fund": series_payload(downsample(risk.drawdown_series(sl)))}}
    if bench is not None and not bench.empty:
        bsl, bwhy = window_slice(bench, sl.index[-1], years)
        if not bwhy and len(bsl) > 2:
            b = bsl.reindex(sl.index, method="ffill").dropna()
            if len(b) > 2:
                out["cumulative"]["category_average"] = series_payload(downsample(b / b.iloc[0] * 100))
                out["drawdown"]["category_average"] = series_payload(downsample(risk.drawdown_series(b)))
    full = clean_nav(nav)
    out["rolling"] = {}
    for y in (1, 3):
        rr = perf.rolling_returns(full, y)
        if years is not None:
            rr = rr[rr.index >= sl.index[0]]
        if not rr.empty:
            out["rolling"][f"{y}y"] = series_payload(downsample(rr), 2)
    rv = risk.rolling_volatility(returns(full), 252)
    if years is not None:
        rv = rv[rv.index >= sl.index[0]]
    out["rolling_volatility_1y"] = series_payload(downsample(rv), 2) if not rv.empty else []
    return out


def analyse(nav: pd.Series, benchmark: pd.Series | None = None, rf: pd.Series | float | None = None, *, rf_label: str = "none",
            benchmark_label: str = "none") -> dict:
    """All metrics for one fund. `benchmark` is a NAV-like index; `rf` is a per-period return series or an annual rate."""
    nav = clean_nav(nav)
    if len(nav) < 30:
        return {"available": False, "reason": "fewer than 30 NAV observations", "methodology_version": METHODOLOGY_VERSION}
    end = nav.index[-1]
    trailing = perf.trailing_returns(nav)
    for label, m in list(trailing.items()):  # a trailing window that spans a suspect NAV jump is not reported
        if m.value is not None and m.window_start is not None:
            hit = [(t, v) for t, v in suspect_moves(nav) if m.window_start <= t.date() <= end.date()]
            if hit:
                trailing[label] = Metric(m.name, None, m.unit, m.window_start, m.window_end, m.n_obs, m.coverage,
                                         f"spans a {hit[0][1] * 100:+.0f}% NAV move on {hit[0][0].date()} (probable split or data error)")
    out: dict = {
        "available": True, "methodology_version": METHODOLOGY_VERSION, "data_issues": [
            {"date": t.date().isoformat(), "move_pct": round(v * 100, 1)} for t, v in suspect_moves(nav)],
        "conventions": conventions(rf_label, benchmark_label),
        "data_window": {"start": nav.index[0].date().isoformat(), "end": end.date().isoformat(), "observations": len(nav)},
        "trailing_returns": {k: v.to_dict() for k, v in trailing.items()},
        "calendar_returns": perf.calendar_returns(nav),
        "windows": [risk_block(nav, end, y, benchmark, rf) for y in WINDOWS],
        "positive_months": _d(perf.positive_period_frequency(nav)),
        "rolling": {},
    }
    for y in (1, 3):
        rr = perf.rolling_returns(nav, y)
        summ = perf.rolling_summary(rr)
        if benchmark is not None and not benchmark.empty:
            br = perf.rolling_returns(benchmark, y)
            summ["pct_outperform_benchmark"] = _d(perf.outperformance_frequency(rr, br))
        out["rolling"][f"{y}y"] = summ
    return out
