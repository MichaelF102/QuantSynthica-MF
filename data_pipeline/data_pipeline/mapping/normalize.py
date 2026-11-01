"""Name normalisation for matching abbreviated source names to official scheme names.

The abbreviation dictionary is versioned: changing it can change mappings, so bump MATCHER_VERSION
in matcher.py when you edit it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# source abbreviation -> expansion (may be several words)
ABBREVIATIONS: dict[str, str] = {
    "dir": "direct", "dr": "direct", "gr": "growth", "grw": "growth", "reg": "regular", "pru": "prudential",
    "bsl": "birla sun life", "mn": "monthly", "mly": "monthly", "qt": "quarterly", "wk": "weekly", "dl": "daily",
    "hy": "half yearly", "ann": "annual", "hyb": "hybrid", "shrt": "short", "ultr": "ultra", "agrsv": "aggressive",
    "agg": "aggressive", "bns": "bonus", "fin": "financial", "adv": "advantage", "advtg": "advantage",
    "cnsrv": "conservative", "cnsv": "conservative", "consv": "conservative", "cons": "conservative",
    "dur": "duration", "corp": "corporate", "eq": "equity", "bd": "bond", "bnd": "bond", "dbt": "debt",
    "fl": "floating", "svcs": "services", "srvs": "services", "serv": "services", "fd": "fund", "allc": "allocation",
    "actv": "active", "lg": "large", "pl": "plan", "pasv": "passive", "arbtg": "arbitrage", "arbtrg": "arbitrage",
    "mat": "maturity", "indiv": "individual", "trm": "term", "inc": "income", "instl": "institutional",
    "invst": "investment", "opp": "opportunities", "bkg": "banking", "bnk": "banking", "bnkg": "banking",
    "glt": "gilt", "pen": "pension", "grp": "group", "sav": "savings", "mgd": "managed", "bal": "balanced",
    "infra": "infrastructure", "ret": "retirement", "retmnt": "retirement", "tax": "tax", "ftp": "fixed term plan",
    "fmp": "fixed maturity plan", "sr": "series", "gld": "gold", "wld": "world", "ovrs": "overseas", "mng": "mining",
    "fof": "fund of funds", "etf": "etf", "ind": "india", "intl": "international", "div": "idcw", "dividend": "idcw",
    "mid": "mid", "sm": "small", "cp": "cap", "sec": "securities", "mkt": "market", "gov": "government",
    "govt": "government", "tr": "treasury", "ovn": "overnight", "liq": "liquid", "lt": "long term", "st": "short term",
    "med": "medium", "ex": "ex", "nxt": "next", "mf": "mutual fund", "co": "", "ltd": "", "limited": "",
}

# Tokens that carry plan/option/frequency information, not fund identity.
PLAN_WORDS = {"direct", "regular", "institutional", "retail", "plan", "option"}
OPTION_WORDS = {"growth", "idcw", "payout", "reinvestment", "reinvest", "transfer", "bonus", "dividend", "income",
                "distribution", "cum", "capital", "withdrawal"}
FREQ_WORDS = {"daily", "weekly", "fortnightly", "monthly", "quarterly", "annual", "yearly", "half", "halfyearly"}
STOP = {"fund", "scheme", "the", "of", "and", "a", "an", "p", "r", "w", "reg", "-"}

FREQ_NORMAL = {"daily": "daily", "weekly": "weekly", "fortnightly": "fortnightly", "monthly": "monthly",
               "quarterly": "quarterly", "annual": "annual", "yearly": "annual", "half yearly": "half_yearly",
               "halfyearly": "half_yearly"}

_MODE_LETTER = {"p": "payout", "r": "reinvestment", "t": "transfer"}
_SPECIAL = {
    # compact source suffixes
    "idcwp": ["idcw", "payout"], "idcwr": ["idcw", "reinvestment"], "diridcwp": ["direct", "idcw", "payout"],
    "diridcwr": ["direct", "idcw", "reinvestment"], "idcwt": ["idcw", "transfer"],
}


def tokens(name: str) -> list[str]:
    s = name.lower().replace("&", " and ").replace("’", "'")
    s = re.sub(r"\bs\s*/\s*t\b", " short term ", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    out: list[str] = []
    prev = ""
    for t in s.split():
        if t in _SPECIAL:
            out.extend(_SPECIAL[t])
        elif prev == "idcw" and t in _MODE_LETTER:  # "IDCW-P" / "IDCW-R" / "IDCW-T"
            out.append(_MODE_LETTER[t])
        else:
            out.extend(ABBREVIATIONS.get(t, t).split())
        prev = out[-1] if out else ""
    return [t for t in out if t]


@dataclass(frozen=True)
class Parsed:
    core: tuple[str, ...]  # identity tokens (plan/option/frequency removed)
    plan: str | None  # Direct | Regular | Institutional | None
    option: str | None  # Growth | IDCW | None
    idcw_modes: frozenset[str]  # subset of {"payout", "reinvest", "other"}
    freq: str | None
    bonus: bool


def parse_name(name: str, extra: str = "") -> Parsed:
    toks = tokens(f"{name} {extra}")
    s = set(toks)
    plan = "Direct" if "direct" in s else "Institutional" if "institutional" in s else "Regular" if "regular" in s else None
    if "growth" in s and not ({"idcw", "payout", "reinvestment"} & s):
        option = "Growth"
    elif {"idcw", "payout", "reinvestment", "reinvest"} & s:
        option = "IDCW"
    elif "growth" in s:
        option = "Growth"
    else:
        option = None
    modes: set[str] = set()
    if "payout" in s:
        modes.add("payout")
    if "reinvestment" in s or "reinvest" in s:
        modes.add("reinvest")
    if "transfer" in s:
        modes.add("other")
    freq = None
    joined = " ".join(toks)
    for key in ("half yearly", "halfyearly", "fortnightly", "quarterly", "monthly", "weekly", "daily", "annual", "yearly"):
        if key in joined:
            freq = FREQ_NORMAL[key]
            break
    core = tuple(t for t in toks if t not in PLAN_WORDS and t not in OPTION_WORDS and t not in FREQ_WORDS
                 and t not in STOP and t not in {"half"})
    return Parsed(core, plan, option, frozenset(modes), freq, "bonus" in s)


def token_score(a: tuple[str, ...], b: tuple[str, ...]) -> float:
    """Symmetric fuzzy overlap in [0,1]. Exact token=1, prefix=0.9, subsequence (same first letter)=0.6."""
    if not a or not b:
        return 0.0

    def sim(x: str, y: str) -> float:
        if x == y:
            return 1.0
        if len(x) >= 3 and (y.startswith(x) or x.startswith(y)):
            return 0.9
        if len(x) >= 3 and x[0] == y[0] and _is_subsequence(x, y):
            return 0.6
        return 0.0

    def directed(p: tuple[str, ...], q: tuple[str, ...]) -> float:
        remaining = list(q)
        total = 0.0
        for x in p:
            best, idx = 0.0, -1
            for i, y in enumerate(remaining):
                v = sim(x, y)
                if v > best:
                    best, idx = v, i
            if idx >= 0:
                total += best
                remaining.pop(idx)
        return total / len(p)

    # conservative: an extra word on either side (e.g. "Ultra" in "Ultra Short Term") must lower the score
    return min(directed(a, b), directed(b, a))


def _is_subsequence(small: str, big: str) -> bool:
    it = iter(big)
    return all(ch in it for ch in small)
