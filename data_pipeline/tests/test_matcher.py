from datetime import date

from data_pipeline.mapping.matcher import SourceFund, estimate_snapshot_date, match_all
from data_pipeline.mapping.normalize import parse_name, tokens
from data_pipeline.sources.amfi import AmfiRecord

D = date(2026, 10, 30)


def rec(code, name, plan, option, nav, isin1="INF000A00001", isin2=None, amc="Axis Mutual Fund"):
    return AmfiRecord(code, name, plan, option, isin1, isin2, nav, D, amc, "cat")


def src(symbol, name, plan="Direct", option="Growth", mode=None, freq=None, price=10.0, amc="Axis Asset Management Company Limited", insurer=False):
    return SourceFund(symbol, name, amc, "cat", plan, option, mode, freq, price, insurer)


def run(funds, records, **kw):
    res, _ = match_all(funds, records, **kw)
    return {m.symbol: m for m in res}


# ---------- normalisation
def test_abbreviations_expand():
    assert tokens("ICICI Pru Cnsv Hyb Dir HY IDCW-R") == ["icici", "prudential", "conservative", "hybrid", "direct", "half", "yearly", "idcw", "reinvestment"]
    assert tokens("Aditya BSL Value Dir Gr")[:4] == ["aditya", "birla", "sun", "life"]


def test_name_parsing_separates_identity_from_plan_option():
    p = parse_name("Axis Midcap Fund - Direct Plan - IDCW Payout Monthly")
    assert p.core == ("axis", "midcap") and p.plan == "Direct" and p.option == "IDCW" and p.freq == "monthly" and p.idcw_modes == {"payout"}
    assert parse_name("X Growth Option").option == "Growth"


def test_extra_word_lowers_the_score():
    from data_pipeline.mapping.normalize import token_score
    assert token_score(("tata", "ultra", "short", "term"), ("tata", "short", "term")) < 0.8
    assert token_score(("tata", "short", "term"), ("tata", "short", "term")) == 1.0


# ---------- matching
def test_growth_matches_exact_nav_and_plan_is_a_hard_constraint():
    records = [rec("1", "Axis Bluechip Fund", "Direct Plan", "Growth", 55.12), rec("2", "Axis Bluechip Fund", "Regular Plan", "Growth", 55.12)]
    m = run([src("S1", "Axis Bluechip Dir Gr", price=55.12)], records)["S1"]
    assert (m.status, m.amfi_code, m.variant) == ("confirmed", "1", "growth")


def test_idcw_payout_and_reinvest_rows_share_one_code_without_conflict():
    records = [rec("7", "Axis Bluechip Fund", "Direct Plan", "IDCW", 18.11, "INF1", "INF2")]
    res = run([src("P", "Axis Bluechip Dir IDCW-P", option="IDCW", mode="Payout", price=18.11),
               src("R", "Axis Bluechip Dir IDCW-R", option="IDCW", mode="Reinvestment", price=18.11)], records)
    assert res["P"].status == res["R"].status == "confirmed"
    assert res["P"].amfi_code == res["R"].amfi_code == "7"
    assert {res["P"].variant, res["R"].variant} == {"idcw_payout", "idcw_reinvest"}


def test_two_rows_cannot_claim_the_same_slot():
    records = [rec("1", "Axis Bluechip Fund", "Direct Plan", "Growth", 55.12)]
    res = run([src("A", "Axis Bluechip Dir Gr", price=55.12), src("B", "Axis Bluechip Dir Gr", price=55.12)], records)
    assert res["A"].status == res["B"].status == "ambiguous"


def test_same_name_different_schemes_resolved_by_nav():
    records = [rec("10", "Axis Children's Fund", "Direct Plan", "Growth", 29.19), rec("11", "Axis Children's Fund", "Direct Plan", "Growth", 29.75)]
    m = run([src("S", "Axis Children's Dir Gr", price=29.75)], records)["S"]
    assert (m.status, m.amfi_code) == ("confirmed", "10" if False else "11")


def test_identical_candidates_are_ambiguous_not_guessed():
    records = [rec("10", "Axis Children's Fund", "Direct Plan", "Growth", 29.19), rec("11", "Axis Children's Fund", "Direct Plan", "Growth", 29.19)]
    m = run([src("S", "Axis Children's Dir Gr", price=29.19)], records)["S"]
    assert m.status == "ambiguous" and len(m.alternatives) == 2


def test_frequency_is_a_hard_constraint():
    records = [rec("1", "Axis Liquid Fund - Weekly IDCW", "Direct Plan", "IDCW", 1000.5, "A", "B"),
               rec("2", "Axis Liquid Fund - Monthly IDCW", "Direct Plan", "IDCW", 1000.5, "C", "D")]
    m = run([src("S", "Axis Liquid Dir Mn IDCW-R", option="IDCW", mode="Reinvestment", freq="Monthly", price=1000.5)], records)["S"]
    assert m.amfi_code == "2"


def test_insurer_without_amc_is_not_an_amfi_scheme_not_dropped():
    m = run([src("U", "Bajaj Life - Pure Equity", plan="Unspecified", option="Unspecified", amc="Bajaj Life Insurance Limited", insurer=True)],
            [rec("1", "Axis Bluechip Fund", "Direct Plan", "Growth", 10.0)])["U"]
    assert m.status == "not_amfi_scheme"


def test_no_candidate_is_unmapped_and_kept():
    m = run([src("S", "Axis Completely Different Strategy Dir Gr")], [rec("1", "Axis Bluechip Fund", "Direct Plan", "Growth", 10.0)])["S"]
    assert m.status == "unmapped"


def test_name_match_with_wrong_nav_is_not_confirmed():
    records = [rec("1", "Axis Bluechip Fund", "Direct Plan", "Growth", 80.0)]
    m = run([src("S", "Axis Bluechip Dir Gr", price=55.0)], records)["S"]
    assert m.status != "confirmed"


def test_snapshot_date_uses_history_and_no_history_means_no_evidence():
    records = [rec("1", "Axis Bluechip Fund", "Direct Plan", "Growth", 80.0)]
    snap = date(2026, 10, 20)
    hist = {"1": {snap: 55.12}}
    m = run([src("S", "Axis Bluechip Dir Gr", price=55.12)], records, nav_lookup=hist.get, snapshot=snap)["S"]
    assert m.status == "confirmed" and m.evidence_date == snap and m.nav_diff < 0.0051
    m = run([src("S", "Axis Bluechip Dir Gr", price=80.0)], records, nav_lookup=lambda c: None, snapshot=snap)["S"]
    assert m.status != "confirmed"  # latest NAV equals price, but the snapshot is not the latest date


def test_weak_name_with_unique_exact_nav_is_only_probable():
    # a renamed scheme: names share only the family prefix, but the NAV matches to the cent on the snapshot date
    records = [rec("1", "Nippon India Corporate Bond Fund", "Direct Plan", "Growth", 33.33, amc="Nippon India Mutual Fund"),
               rec("2", "Nippon India Small Cap Fund", "Direct Plan", "Growth", 44.44, amc="Nippon India Mutual Fund")]
    f = src("S", "Nippon India Credit Risk Dir Gr", price=33.33, amc="Nippon Life India Asset Management Ltd")
    m = run([f], records)["S"]
    assert m.status == "probable" and m.amfi_code == "1" and m.method.endswith("weak_name")


def test_manual_override_wins_and_unknown_override_is_reported():
    records = [rec("1", "Axis Bluechip Fund", "Direct Plan", "Growth", 10.0)]
    res = run([src("A", "Totally Unrelated Name", price=1.0), src("B", "x", price=1.0)], records, code_overrides={"A": "1", "B": "999"})
    assert res["A"].status == "confirmed" and res["A"].method == "manual_override"
    assert res["B"].status == "unmapped" and "unknown_code" in res["B"].method


def test_amc_override():
    records = [rec("1", "Zeta Bluechip Fund", "Direct Plan", "Growth", 10.0, amc="Zeta Mutual Fund")]
    f = src("S", "Zeta Bluechip Dir Gr", price=10.0, amc="Weird Holding Name Pvt")
    assert run([f], records)["S"].status == "not_amfi_scheme" or run([f], records)["S"].status == "unmapped"
    assert run([f], records, amc_overrides={"Weird Holding Name Pvt": "Zeta Mutual Fund"})["S"].status == "confirmed"


# ---------- snapshot date estimation
def test_estimate_snapshot_date_picks_the_consensus_date():
    d1, d2 = date(2026, 10, 20), date(2026, 10, 21)
    pairs = [(10.0 + i, {d1: 10.0 + i, d2: 11.0 + i}) for i in range(40)]
    assert estimate_snapshot_date(pairs) == (d1, 40, 40)


def test_estimate_snapshot_date_requires_enough_votes():
    pairs = [(10.0, {date(2026, 10, 20): 10.0})]
    assert estimate_snapshot_date(pairs)[0] is None
