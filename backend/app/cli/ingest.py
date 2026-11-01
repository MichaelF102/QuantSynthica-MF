"""python -m app.cli.ingest [--path data/raw/yahoo/yahoo_funds_clean.csv] [--force]"""
import argparse
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db import session_factory
from app.services.ingest_yahoo import ingest_yahoo_csv

DEFAULT = Path(__file__).resolve().parents[3] / "data" / "raw" / "yahoo" / "yahoo_funds_clean.csv"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--path", type=Path, default=DEFAULT)
    p.add_argument("--force", action="store_true", help="ingest even if this exact file was already loaded")
    args = p.parse_args()
    configure_logging(get_settings().log_level)
    with session_factory()() as session:
        run = ingest_yahoo_csv(session, args.path, force=args.force)
    print(
        f"run={run.id} status={run.status} rows={run.rows_read} inserted={run.schemes_inserted} "
        f"updated={run.schemes_updated} unchanged={run.schemes_unchanged} quarantined={run.rows_quarantined}"
    )


if __name__ == "__main__":
    main()
