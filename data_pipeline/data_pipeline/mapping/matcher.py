"""Map source-snapshot funds to official AMFI scheme codes.

Design rules
- Plan, option, IDCW mode and IDCW frequency are hard constraints when both sides state them.
- An AMFI scheme code can legitimately serve several source rows: one IDCW code covers both payout and
  reinvestment (same NAV), which the source lists as two rows. Uniqueness is therefore per
  (amfi_code, variant), variant in {growth, idcw_payout, idcw_reinvest, idcw_other}.
- NAV agreement is evidence, not a filter. Exact agreement (to the source's 2-decimal rounding) on the
  snapshot date is the strongest evidence; when the date is unknown the latest NAV is used with a looser tier.
- Ambiguity and non-matches are reported, never silently resolved or dropped.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date

from data_pipeline.mapping.normalize import Parsed, parse_name, token_score, tokens
from data_pipeline.sources.amfi import AmfiRecord

MATCHER_VERSION = "1.0.0"
EXACT_ABS = 0.0051  # source prices are rounded to 2 decimals
NEAR_REL = 0.03
MIN_NAME = 0.5
AMC_STOP = {"mutual", "fund", "funds", "asset", "asst", "management", "mgmt", "co", "ltd", "limited", "pvt", "private",
            "india", "ind", "company", "amc", "life", "insurance", "managers", "money", "investment", "advisors",
            "portfolio"}
ALL_VARIANTS = frozenset({"growth", "idcw_payout", "idcw_reinvest", "idcw_other"})


@dataclass(frozen=True)
class SourceFund:
    symbol: str
    name: str
    amc: str
    category: str
    plan_type: str  # Direct | Regular | Institutional | Unspecified
    option_type: str  # Growth | IDCW | Unspecified
    idcw_mode: str | None  # Payout | Reinvestment | Transfer | None
    idcw_freq: str | None
    price: float | None
    is_insurer: bool = False


@dataclass
class Candidate:
    amfi_code: str
    variant: str
    name_score: float
    tier: int  # 2 exact, 1 near, 0 none
    nav: float | None
    nav_diff: float | None  # absolute
    nav_date: date | None
    amfi_name: str


@dataclass
class Mapping_:
    symbol: str
    status: str  # confirmed | probable | name_only | ambiguous | unmapped | not_amfi_scheme
    amfi_code: str | None = None
    variant: str | None = None
    name_score: float | None = None
    nav_tier: int | None = None
    nav_diff: float | None = None
    evidence_date: date | None = None
    method: str = ""
    alternatives: list[dict] = field(default_factory=list)


def amc_key(name: str) -> tuple[str, ...]:
    return tuple(t for t in tokens(name) if t not in AMC_STOP)


def build_amc_map(source_amcs: Iterable[str], amfi_amcs: Iterable[str], overrides: Mapping[str, str] | None = None) -> dict[str, str | None]:
    """Source AMC string -> AMFI AMC string (or None). Reviewable; overrides win."""
    overrides = overrides or {}
    amfi_list = sorted({a for a in amfi_amcs if a})
    keys = {a: amc_key(a) for a in amfi_list}
    out: dict[str, str | None] = {}
    for s in sorted(set(source_amcs)):
        if s in overrides:
            out[s] = overrides[s] or None
            continue
        sk = amc_key(s)
        best, score = None, 0.0
        for a, ak in keys.items():
            sc = token_score(sk, ak)
            if sc > score:
                best, score = a, sc
        out[s] = best if score >= 0.8 else None
    return out


def _amfi_variants(p: Parsed, rec: AmfiRecord) -> frozenset[str]:
    if p.option == "Growth":
        return frozenset({"growth"})
    if p.option == "IDCW":
        if rec.isin_primary and rec.isin_reinvest:  # one code lists both payout and reinvestment ISINs
            return frozenset({"idcw_payout", "idcw_reinvest", "idcw_other"})
        if p.idcw_modes:
            return frozenset({"idcw_payout" if m == "payout" else "idcw_reinvest" if m == "reinvest" else "idcw_other" for m in p.idcw_modes})
        if rec.isin_primary:
            return frozenset({"idcw_payout", "idcw_other"})
        return frozenset({"idcw_payout", "idcw_reinvest", "idcw_other"})
    return ALL_VARIANTS  # unknown option on legacy entries


def _source_variants(f: SourceFund, p: Parsed) -> frozenset[str] | None:
    opt = f.option_type if f.option_type != "Unspecified" else (p.option or "Unspecified")
    if opt == "Growth":
        return frozenset({"growth"})
    if opt == "IDCW":
        mode = (f.idcw_mode or "").lower()
        if mode.startswith("pay"):
            return frozenset({"idcw_payout"})
        if mode.startswith("re"):
            return frozenset({"idcw_reinvest"})
        if mode.startswith("tr"):  # transfer shares the IDCW scheme code and NAV
            return frozenset({"idcw_other", "idcw_payout", "idcw_reinvest"})
        if p.idcw_modes:
            return frozenset({"idcw_payout" if m == "payout" else "idcw_reinvest" if m == "reinvest" else "idcw_other" for m in p.idcw_modes})
        return frozenset({"idcw_payout", "idcw_reinvest", "idcw_other"})
    return None  # unknown


@dataclass
class _Indexed:
    rec: AmfiRecord
    parsed: Parsed
    variants: frozenset[str]


def index_amfi(records: Iterable[AmfiRecord]) -> dict[str, list[_Indexed]]:
    by_amc: dict[str, list[_Indexed]] = defaultdict(list)
    for r in records:
        p = parse_name(r.name, f"{r.plan or ''} {r.option or ''}")
        by_amc[r.amc or ""].append(_Indexed(r, p, _amfi_variants(p, r)))
    return by_amc


NavLookup = Callable[[str], Mapping[date, float]]


def _evidence(price: float | None, rec: AmfiRecord, hist: Mapping[date, float] | None, snapshot: date | None):
    """Return (tier, nav, diff, date)."""
    if price is None:
        return 0, rec.nav, None, rec.nav_date
    if snapshot is not None:
        # The snapshot date is known: only the NAV on that date is comparable. No history -> no evidence.
        if not hist or snapshot not in hist:
            return 0, None, None, None
        nav = hist[snapshot]
        d = abs(nav - price)
        tier = 2 if d <= EXACT_ABS else 1 if d / price <= NEAR_REL else 0
        return tier, nav, d, snapshot
    if rec.nav is None:
        return 0, None, None, rec.nav_date
    d = abs(rec.nav - price)
    tier = 2 if d <= EXACT_ABS else 1 if d / price <= NEAR_REL else 0
    # without a known snapshot date a latest-NAV match is weaker evidence than a dated one
    return tier, rec.nav, d, rec.nav_date


def candidates_for(f: SourceFund, pool: list[_Indexed], nav_lookup: NavLookup | None = None, snapshot: date | None = None) -> list[Candidate]:
    sp = parse_name(f.name)
    sv = _source_variants(f, sp)
    out: list[Candidate] = []
    for ix in pool:
        ap = ix.parsed
        if f.plan_type != "Unspecified" and ap.plan and ap.plan != f.plan_type:
            continue
        if f.plan_type == "Unspecified" and sp.plan and ap.plan and sp.plan != ap.plan:
            continue
        if sv is not None and not (sv & ix.variants):
            continue
        freq = f.idcw_freq.lower() if f.idcw_freq else sp.freq
        if freq and ap.freq and freq.replace(" ", "_") != ap.freq:
            continue
        if sp.bonus != ap.bonus:
            continue
        score = token_score(sp.core, ap.core)
        if score < MIN_NAME:
            continue
        variant = sorted(sv & ix.variants)[0] if sv is not None else sorted(ix.variants)[0]
        hist = nav_lookup(ix.rec.code) if nav_lookup else None
        tier, nav, diff, nd = _evidence(f.price, ix.rec, hist, snapshot)
        out.append(Candidate(ix.rec.code, variant, round(score, 4), tier, nav, diff, nd, ix.rec.name))
    out.sort(key=lambda c: (c.tier, c.name_score), reverse=True)
    return out


def match_all(
    funds: list[SourceFund], records: Iterable[AmfiRecord], *, amc_overrides: Mapping[str, str] | None = None,
    code_overrides: Mapping[str, str] | None = None, nav_lookup: NavLookup | None = None, snapshot: date | None = None,
) -> tuple[list[Mapping_], dict[str, str | None]]:
    records = list(records)
    by_amc = index_amfi(records)
    amc_map = build_amc_map((f.amc for f in funds), by_amc.keys(), amc_overrides)
    code_overrides = code_overrides or {}
    by_code = {r.code: r for r in records}
    results: list[Mapping_] = []

    for f in funds:
        if f.symbol in code_overrides:
            code = code_overrides[f.symbol]
            ok = code in by_code
            results.append(Mapping_(f.symbol, "confirmed" if ok else "unmapped", code if ok else None, None, 1.0, None, None, None,
                                    "manual_override" if ok else "manual_override_unknown_code"))
            continue
        amfi_amc = amc_map.get(f.amc)
        if amfi_amc is None:
            results.append(Mapping_(f.symbol, "not_amfi_scheme" if f.is_insurer else "unmapped", method="no_amc_match"))
            continue
        cands = candidates_for(f, by_amc[amfi_amc], nav_lookup, snapshot)
        results.append(_decide(f, cands))

    _resolve_slot_conflicts(results)
    return results, amc_map


def _alts(cands: list[Candidate], n: int = 3) -> list[dict]:
    return [{"amfi_code": c.amfi_code, "name": c.amfi_name, "name_score": c.name_score, "nav_tier": c.tier,
             "nav_diff": c.nav_diff} for c in cands[:n]]


def _decide(f: SourceFund, cands: list[Candidate]) -> Mapping_:
    if not cands:
        return Mapping_(f.symbol, "not_amfi_scheme" if f.is_insurer else "unmapped", method="no_candidate")
    best = cands[0]
    rivals = [c for c in cands[1:] if c.amfi_code != best.amfi_code]
    second = rivals[0] if rivals else None
    base = dict(symbol=f.symbol, amfi_code=best.amfi_code, variant=best.variant, name_score=best.name_score,
                nav_tier=best.tier, nav_diff=best.nav_diff, evidence_date=best.nav_date, alternatives=_alts(cands))
    if best.tier == 2 and best.name_score >= 0.8:
        tied = second is not None and second.tier == 2 and second.name_score >= best.name_score - 0.05
        return Mapping_(status="ambiguous" if tied else "confirmed", method="name+plan+option+exact_nav", **base)
    if best.tier == 1 and best.name_score >= 0.85:
        close = second is not None and second.tier >= 1 and second.name_score >= best.name_score - 0.05
        return Mapping_(status="ambiguous" if close else "probable", method="name+plan+option+near_nav", **base)
    if best.tier == 2 and best.name_score >= 0.5 and not [c for c in rivals if c.tier == 2]:
        # exact NAV agreement on the snapshot date with a unique candidate, but the names differ (likely a rename)
        return Mapping_(status="probable", method="exact_nav_unique+weak_name", **base)
    if best.name_score >= 0.9:
        close = second is not None and second.name_score >= best.name_score - 0.1
        return Mapping_(status="ambiguous" if close else "name_only", method="name+plan+option", **base)
    return Mapping_(f.symbol, "unmapped", method="low_name_score", alternatives=_alts(cands))


def _resolve_slot_conflicts(results: list[Mapping_]) -> None:
    """Two source rows may not claim the same (code, variant). Keep the clearly better one, else both ambiguous."""
    slots: dict[tuple[str, str], list[Mapping_]] = defaultdict(list)
    for m in results:
        if m.amfi_code and m.variant and m.status in {"confirmed", "probable", "name_only"}:
            slots[(m.amfi_code, m.variant)].append(m)
    for group in slots.values():
        if len(group) < 2:
            continue
        group.sort(key=lambda m: ((m.nav_tier or 0), m.name_score or 0), reverse=True)
        top, rest = group[0], group[1:]
        clear = (top.nav_tier or 0) > (rest[0].nav_tier or 0) or (top.name_score or 0) - (rest[0].name_score or 0) >= 0.1
        for m in (rest if clear else group):
            m.status = "ambiguous"
            m.method += "+slot_conflict"


def estimate_snapshot_date(pairs: Iterable[tuple[float, Mapping[date, float]]], min_votes: int = 30) -> tuple[date | None, int, int]:
    """Date on which most source prices equal the official NAV (to rounding).

    `pairs` are (source price, {date: nav}) for high-confidence name matches. Returns (date, votes, pairs_used).
    """
    votes: dict[date, int] = defaultdict(int)
    n = 0
    for price, hist in pairs:
        n += 1
        for d, nav in hist.items():
            if abs(nav - price) <= EXACT_ABS:
                votes[d] += 1
    if not votes:
        return None, 0, n
    d, v = max(votes.items(), key=lambda kv: (kv[1], kv[0]))
    return (d if v >= min_votes else None), v, n


def top_candidate_codes(funds: list[SourceFund], records: Iterable[AmfiRecord], *, k: int = 3, min_name: float = 0.7,
                        amc_overrides: Mapping[str, str] | None = None) -> set[str]:
    """Codes worth fetching NAV history for: the best name-based candidates of every non-insurer source fund."""
    by_amc = index_amfi(records)
    amc_map = build_amc_map((f.amc for f in funds), by_amc.keys(), amc_overrides)
    codes: set[str] = set()
    for f in funds:
        a = amc_map.get(f.amc)
        if a is None:
            continue
        ranked = sorted(candidates_for(f, by_amc[a]), key=lambda c: c.name_score, reverse=True)
        codes.update(c.amfi_code for c in ranked[:k] if c.name_score >= min_name)
    return codes
