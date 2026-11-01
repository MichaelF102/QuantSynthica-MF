from datetime import date, timedelta

import pytest
from data_pipeline.nav.quality import check_series

pq = pytest.importorskip("pyarrow")
from data_pipeline.nav.store import NavStore

D = date(2026, 1, 5)


def rules(issues):
    return [i.rule for i in issues]


def test_clean_series_has_no_issues():
    obs = [(D + timedelta(days=i), 10 + i * 0.01) for i in range(30)]
    clean, issues = check_series(obs, today=date(2026, 12, 31))
    assert len(clean) == 30 and issues == []


def test_invalid_nav_flagged_and_excluded():
    clean, issues = check_series([(D, 10.0), (D + timedelta(days=1), None), (D + timedelta(days=2), 0.0), (D + timedelta(days=3), -1.0)], today=date(2026, 12, 31))
    assert [d for d, _ in clean] == [D]
    assert rules(issues).count("N010_invalid_nav") == 3


def test_conflicting_duplicate_is_withheld_not_resolved():
    clean, issues = check_series([(D, 10.0), (D, 10.5), (D + timedelta(days=1), 10.1)], today=date(2026, 12, 31))
    assert [d for d, _ in clean] == [D + timedelta(days=1)]
    assert "N012_conflicting_duplicate" in rules(issues)


def test_identical_duplicate_collapses():
    clean, issues = check_series([(D, 10.0), (D, 10.0)], today=date(2026, 12, 31))
    assert clean == [(D, 10.0)] and rules(issues) == ["N013_duplicate_same_value"]


def test_gap_jump_and_future_date_flagged_but_values_kept():
    obs = [(D, 10.0), (D + timedelta(days=20), 10.0), (D + timedelta(days=21), 15.0), (date(2030, 1, 1), 15.0)]
    clean, issues = check_series(obs, today=date(2026, 12, 31))
    r = rules(issues)
    assert "N020_gap" in r and "N021_large_move" in r and "N011_future_date" in r
    assert len(clean) == 4  # nothing is silently deleted


def test_stale_run_reported():
    obs = [(D + timedelta(days=i), 10.0) for i in range(40)]
    _, issues = check_series(obs, today=date(2026, 12, 31))
    assert "N022_stale_run" in rules(issues)


def test_unsorted_input_is_sorted():
    clean, _ = check_series([(D + timedelta(days=2), 3.0), (D, 1.0), (D + timedelta(days=1), 2.0)], today=date(2026, 12, 31))
    assert [v for _, v in clean] == [1.0, 2.0, 3.0]


# ---- parquet store
def rows(code="1", n=5, start=D, nav=10.0):
    return [(code, start + timedelta(days=i), nav + i, "t") for i in range(n)]


def test_store_upsert_is_idempotent(tmp_path):
    st = NavStore(tmp_path)
    assert st.upsert(rows()) == {"inserted": 5, "updated": 0, "unchanged": 0}
    assert st.upsert(rows()) == {"inserted": 0, "updated": 0, "unchanged": 5}
    assert st.row_count() == 5


def test_store_updates_changed_values_and_adds_new(tmp_path):
    st = NavStore(tmp_path)
    st.upsert(rows())
    c = st.upsert(rows(nav=20.0)[:2] + rows(start=D + timedelta(days=5), n=2))
    assert c == {"inserted": 2, "updated": 2, "unchanged": 0}
    s = st.read(["1"])["1"]
    assert len(s) == 7 and s[0] == (D, 20.0) and s == sorted(s)


def test_store_partitions_by_year_and_filters_reads(tmp_path):
    st = NavStore(tmp_path)
    st.upsert([("1", date(2024, 12, 31), 1.0, "t"), ("1", date(2025, 1, 1), 2.0, "t"), ("2", date(2025, 1, 1), 3.0, "t")])
    assert sorted(p.name for p in tmp_path.glob("year=*")) == ["year=2024", "year=2025"]
    assert st.read(["2"]) == {"2": [(date(2025, 1, 1), 3.0)]}
    assert st.read(start=date(2025, 1, 1))["1"] == [(date(2025, 1, 1), 2.0)]
    assert st.read(["9"]) == {}


def test_store_never_leaves_partial_files(tmp_path):
    st = NavStore(tmp_path)
    st.upsert(rows())
    assert not list(tmp_path.rglob("*.tmp"))


def test_concurrent_writers_do_not_lose_or_corrupt_data(tmp_path):
    import multiprocessing as mp

    ctx = mp.get_context("fork")
    procs = [ctx.Process(target=_writer, args=(str(tmp_path), k)) for k in range(4)]
    for p in procs:
        p.start()
    for p in procs:
        p.join()
        assert p.exitcode == 0
    st = NavStore(tmp_path)
    assert st.row_count() == 4 * 6 * 20  # every writer's rows survive
    assert not list(tmp_path.rglob("*.tmp"))


def _writer(root, k):
    st = NavStore(root)
    for i in range(6):
        st.upsert(rows(code=f"{k}-{i}", n=20))
