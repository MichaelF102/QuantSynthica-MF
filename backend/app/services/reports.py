"""PDF and Excel reports.

A report is built ONCE as a neutral document (title, sections of tables and notes) from the same service functions the
dashboards use, then rendered to Excel or PDF. Numbers are stored raw in the document; formatting happens at render time,
so a test can compare report cells against the API payload exactly.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.services import amc as amc_svc
from app.services import analytics, portfolio

DISCLAIMER = ("For research and education only; not investment advice or a recommendation. Figures are computed from public NAV records and "
              "a proxy risk-free rate and category-average benchmark; surviving funds only. Past performance does not indicate future results.")
KINDS = ("fund", "portfolio", "amc")


class ReportError(ValueError):
    pass


@dataclass
class Table:
    title: str
    columns: list[str]
    rows: list[list[Any]]
    note: str | None = None


@dataclass
class Report:
    title: str
    kind: str
    subtitle: str = ""
    generated: str = field(default_factory=lambda: datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"))
    summary: list[tuple[str, Any]] = field(default_factory=list)
    tables: list[Table] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _v(m: dict | None) -> float | None:
    return None if not isinstance(m, dict) else m.get("value")


# ------------------------------------------------------------------ builders
def fund_report(session: Session, scheme_id: int, years: float | None = 3) -> Report:
    a = analytics.fund_analytics(session, scheme_id, years)
    if a is None:
        raise ReportError("fund not found")
    r = Report(f"Fund report: {a['name']}", "fund", f"{a['category']} · {a['plan_type']} · {a['option_type']}")
    if not a.get("available"):
        r.notes.append(f"Analytics are not available for this fund: {a.get('reason') or a.get('mapping_status')}.")
        r.notes.append(DISCLAIMER)
        return r
    dw = a["data_window"]
    r.summary = [("NAV history start", dw["start"]), ("NAV history end", dw["end"]), ("Observations", dw["observations"]), ("Methodology", a["methodology_version"])]
    r.tables.append(Table("Trailing returns (%)", ["Period", "Return", "Unit", "Window start", "Window end"],
                          [[k.upper(), _v(m), m.get("unit"), m.get("window_start"), m.get("window_end")] for k, m in a["trailing_returns"].items()]))
    r.tables.append(Table("Calendar-year returns (%)", ["Year", "Return", "Partial year"], [[c["year"], c["return"], "yes" if c["partial"] else "no"] for c in a["calendar_returns"]]))
    rows = []
    for w in a["windows"]:
        if w.get("available"):
            rows.append([f"{w['years']}Y"] + [_v(w.get(k)) for k in ("cagr", "volatility", "sharpe_ratio", "sortino_ratio", "max_drawdown", "var_95", "cvar_95")])
    r.tables.append(Table("Risk and return by window", ["Window", "CAGR %", "Volatility %", "Sharpe", "Sortino", "Max drawdown %", "VaR 95 %", "CVaR 95 %"], rows,
                          "Sharpe and Sortino use a proxy risk-free rate; withheld when volatility is too low to be meaningful."))
    r.notes += [f"Benchmark: {a['conventions']['benchmark']}.", f"Risk-free: {a['conventions']['risk_free']}."] + [str(i) for i in a.get("data_issues", [])]
    r.notes.append(DISCLAIMER)
    return r


def portfolio_report(session: Session, holdings: list[dict]) -> Report:
    try:
        p = portfolio.analyze(session, {"holdings": holdings, "years": 3})
    except portfolio.RequestError as exc:
        raise ReportError(str(exc)) from exc
    r = Report("Portfolio report", "portfolio", f"{len(p['funds'])} funds, rebalanced monthly to the stated weights")
    h = p["history"]
    r.summary = [("History start", h["start"]), ("History end", h["end"]), ("Observations", h["observations"]), ("Methodology", p["version"])]
    r.tables.append(Table("Holdings", ["Fund", "Category", "Plan", "Weight %"] + (["Risk share %"] if p.get("risk") else []),
                          [[f["name"], f["category"], f["plan"], f["weight_pct"]] + ([p["risk"]["risk_contribution_pct"][i]] if p.get("risk") else []) for i, f in enumerate(p["funds"])]))
    r.tables.append(Table("Allocation by category (%)", ["Category", "Weight %"], [[x["name"], x["weight_pct"]] for x in p["allocation"]["by_category"]]))
    rows = []
    for w in p["analytics"].get("windows", []):
        if w.get("available"):
            rows.append([f"{w['years']}Y"] + [_v(w.get(k)) for k in ("cagr", "volatility", "sharpe_ratio", "max_drawdown")])
    r.tables.append(Table("Risk and return by window", ["Window", "CAGR %", "Volatility %", "Sharpe", "Max drawdown %"], rows))
    if p.get("risk"):
        r.summary += [("Effective number of funds", p["risk"]["effective_number_of_funds"]), ("Diversification ratio", p["risk"]["diversification_ratio"])]
    r.notes += p["warnings"] + [DISCLAIMER]
    return r


def amc_report(session: Session) -> Report:
    d = amc_svc.ranking(session)
    r = Report("AMC intelligence report", "amc", "Category-adjusted comparison of fund houses (Direct Growth plans)")
    r.summary = [("AMCs ranked", d["eligible"]), ("AMCs listed", len(d["amcs"])), ("Methodology", d["version"])]
    r.tables.append(Table("Fund houses", ["Rank", "AMC", "Funds", "Scored funds", "Categories", "Median score percentile", "Above median %", "Top quartile %", "Bottom quartile %"],
                          [[a["rank"], a["amc"], a["funds"], a["scored_funds"], a["categories"], a["median_score_percentile"], a["share_above_median"],
                            a["share_top_quartile"], a["share_bottom_quartile"]] for a in d["amcs"]], "Blank = not ranked (too few scored funds or categories)."))
    r.notes += d["method"] + ["The underlying score has not shown a net-of-cost selection edge in backtests.", DISCLAIMER]
    return r


def build(session: Session, kind: str, params: dict) -> Report:
    if kind == "fund":
        try:
            sid = int(params["scheme_id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ReportError("scheme_id is required") from exc
        y = params.get("years", 3)
        return fund_report(session, sid, None if y in ("max", None) else float(y))
    if kind == "portfolio":
        if not params.get("holdings"):
            raise ReportError("holdings are required")
        return portfolio_report(session, params["holdings"])
    if kind == "amc":
        return amc_report(session)
    raise ReportError(f"kind must be one of {', '.join(KINDS)}")


# ------------------------------------------------------------------ renderers
def to_xlsx(rep: Report) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font

    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    ws.append([rep.title]); ws["A1"].font = Font(bold=True, size=14)
    ws.append([rep.subtitle]); ws.append(["Generated", rep.generated]); ws.append([])
    for k, v in rep.summary:
        ws.append([k, v])
    ws.append([])
    for n in rep.notes:
        ws.append([n])
    ws.column_dimensions["A"].width = 38; ws.column_dimensions["B"].width = 28
    for i, t in enumerate(rep.tables, 1):
        s = wb.create_sheet(f"{i}. {t.title}"[:31].replace("/", "-").replace(":", ""))
        s.append([t.title]); s["A1"].font = Font(bold=True)
        s.append(t.columns)
        for c in s[2]:
            c.font = Font(bold=True)
        for row in t.rows:
            s.append(row)  # raw numbers, no rounding: the numbers-match test depends on it
        if t.note:
            s.append([]); s.append([t.note])
        for col in range(1, len(t.columns) + 1):
            s.column_dimensions[chr(64 + col)].width = 26
    buf = io.BytesIO(); wb.save(buf)
    return buf.getvalue()


def _fmt(v: Any) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:,.2f}"
    return str(v)


def to_pdf(rep: Report) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, TableStyle
    from reportlab.platypus import Table as RTable

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), title=rep.title, leftMargin=28, rightMargin=28, topMargin=28, bottomMargin=28)
    st = getSampleStyleSheet()
    esc = lambda s: str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")  # noqa: E731
    el = [Paragraph(esc(rep.title), st["Title"]), Paragraph(esc(rep.subtitle), st["Normal"]), Paragraph(f"Generated {rep.generated}", st["Normal"]), Spacer(1, 10)]
    if rep.summary:
        el.append(RTable([[esc(k), _fmt(v)] for k, v in rep.summary], colWidths=[200, 200], style=TableStyle([("FONTSIZE", (0, 0), (-1, -1), 8), ("GRID", (0, 0), (-1, -1), 0.25, colors.grey)])))
    for t in rep.tables:
        el += [Spacer(1, 12), Paragraph(esc(t.title), st["Heading3"])]
        data = [[Paragraph(esc(c), st["BodyText"]) for c in t.columns]] + [[Paragraph(esc(_fmt(x)), st["BodyText"]) for x in row] for row in t.rows]
        el.append(RTable(data, repeatRows=1, style=TableStyle([("FONTSIZE", (0, 0), (-1, -1), 7), ("GRID", (0, 0), (-1, -1), 0.25, colors.grey), ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey)])))
        if t.note:
            el.append(Paragraph(esc(t.note), st["Italic"]))
    el += [Spacer(1, 12), Paragraph("Notes and limitations", st["Heading3"])] + [Paragraph("• " + esc(n), st["BodyText"]) for n in rep.notes]
    doc.build(el)
    return buf.getvalue()
