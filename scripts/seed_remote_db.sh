#!/usr/bin/env bash
# Copy the reference and analytics tables (NOT users, sessions or saved items) from a source database to a destination database
# that already has the schema (run `alembic upgrade head` against it first).
# Usage: SRC=postgresql://... DST=postgresql://... scripts/seed_remote_db.sh
set -euo pipefail
: "${SRC:?}"; : "${DST:?}"
tables=(amcs fund_categories fund_families schemes external_ids fund_snapshots ingestion_runs data_quality_issues amfi_schemes scheme_mappings nav_coverage scheme_metrics fund_scores backtest_runs)
args=(); for t in "${tables[@]}"; do args+=(-t "$t"); done
# --disable-triggers needs superuser on some hosts; the order above already respects foreign keys, so load in order instead.
pg_dump --data-only --no-owner "${args[@]}" "$SRC" | psql -v ON_ERROR_STOP=1 "$DST" >/dev/null
for t in "${tables[@]}"; do
  a=$(psql -tA "$SRC" -c "select count(*) from $t"); b=$(psql -tA "$DST" -c "select count(*) from $t")
  [ "$a" = "$b" ] && echo "ok   $t $a" || { echo "MISMATCH $t src=$a dst=$b" >&2; exit 1; }
done
# sequences: keep ids moving forward on the destination
psql -v ON_ERROR_STOP=1 "$DST" -c "select setval(pg_get_serial_sequence('schemes','id'), (select max(id) from schemes)), setval(pg_get_serial_sequence('amcs','id'), (select max(id) from amcs))" >/dev/null
