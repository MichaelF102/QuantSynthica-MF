"""Phase 3 pipeline CLI.

  python -m app.cli.pipeline master            # official scheme register from the daily NAV file
  python -m app.cli.pipeline recent            # last N days of official NAV history, all schemes (a few requests)
  python -m app.cli.pipeline backfill          # full NAV history for candidate schemes (resumable, slow)
  python -m app.cli.pipeline map               # match source funds to official codes
  python -m app.cli.pipeline quality           # series checks (gaps, jumps, invalid values) on accepted schemes
  python -m app.cli.pipeline validate          # official vs mfapi.in agreement on overlapping dates
  python -m app.cli.pipeline metrics           # NAV-derived metrics + peer percentiles for all eligible schemes
  python -m app.cli.pipeline quant             # score history, fund scores, factor research, clusters, regimes
  python -m app.cli.pipeline coverage          # write the coverage report
  python -m app.cli.pipeline all               # master -> recent -> map -> backfill -> map -> coverage
"""
import argparse
import json

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db import session_factory
from app.services import amfi_master, coverage, mapping, nav_load


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("step", choices=["master", "recent", "backfill", "rebuild", "map", "quality", "validate", "metrics", "quant", "coverage", "all"])
    p.add_argument("--limit", type=int, help="max schemes to fetch in backfill")
    p.add_argument("--workers", type=int, default=3)
    p.add_argument("--refresh-days", type=int, help="re-fetch series whose last date is older than this many days")
    p.add_argument("--days", type=int, default=400, help="how far back the recent step goes")
    p.add_argument("--skip-days", type=int, default=0, help="end the recent step this many days before today (to extend history)")
    p.add_argument("--candidates", type=int, default=3, help="candidates per source fund whose history is fetched")
    a = p.parse_args()
    configure_logging(get_settings().log_level)

    with session_factory()() as s:
        def do_master():
            r = amfi_master.ingest_nav_all(s)
            print(f"master run={r.id} status={r.status} records={r.rows_read} inserted={r.schemes_inserted} updated={r.schemes_updated}")

        def do_recent():
            from datetime import date, timedelta

            end = date.today() - timedelta(days=a.skip_days)
            r = nav_load.official_recent_load(s, date.today() - timedelta(days=a.days), end)
            print(f"recent run={r.id} {json.dumps(r.summary)}")

        def do_rebuild():
            print(f"rebuild {json.dumps(nav_load.rebuild_store(s))}")

        def do_quality():
            from app.services import nav_checks

            print(f"quality {json.dumps(nav_checks.quality_scan(s))}")

        def do_validate():
            from app.services import nav_checks

            print(f"validate {json.dumps(nav_checks.validate_sources(s), default=str)[:600]}")

        def do_metrics():
            from app.services import metrics_batch

            print(f"metrics {json.dumps(metrics_batch.compute_all(s))}")
            from app.services import analytics

            print(f"category benchmarks {analytics.build_benchmarks(s)} groups")

        def do_quant():
            from app.services import quant

            print(f"quant {json.dumps(quant.build_all(s), default=str)}")

        def do_backfill():
            codes = sorted(mapping.candidate_codes(s, k=a.candidates))
            r = nav_load.backfill(s, codes, workers=a.workers, limit=a.limit, refresh_after_days=a.refresh_days)
            print(f"backfill run={r.id} {json.dumps(r.summary)}")

        def do_map():
            r = mapping.run_mapping(s)
            print(f"map run={r.id} {json.dumps(r.summary, indent=1)}")

        def do_cov():
            rep = coverage.write_report(s)
            print(f"coverage written to {coverage.report_path()}")
            print(json.dumps({k: rep.get(k) for k in ("mapping", "nav_history", "snapshot_date")}, indent=1, default=str))

        steps = {"master": [do_master], "recent": [do_recent], "rebuild": [do_rebuild], "backfill": [do_backfill], "map": [do_map],
                 "quality": [do_quality], "validate": [do_validate], "metrics": [do_metrics], "quant": [do_quant], "coverage": [do_cov],
                 "all": [do_master, do_recent, do_map, do_backfill, do_map, do_quality, do_validate, do_metrics, do_quant, do_cov]}[a.step]
        for fn in steps:
            fn()


if __name__ == "__main__":
    main()
