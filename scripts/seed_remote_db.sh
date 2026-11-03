#!/usr/bin/env bash
# Copy the reference and analytics tables (NOT users, sessions or saved items) from a source database to a destination database
# that already has the schema (run `alembic upgrade head` against it first).
# Usage: SRC=postgresql://... DST=postgresql://... scripts/seed_remote_db.sh
set -euo pipefail
: "${SRC:?}"; : "${DST:?}"
# pg_dump's data script empties search_path for its session. Behind a connection pooler (Neon "-pooler" hosts, Supabase pooler on 6543)
# that setting can stay on the shared server connection and break every later client ("no schema has been selected", "relation does not exist").
case "$DST" in *-pooler.*|*pooler.supabase.com:6543*)
  echo "DST is a pooled connection string. Use the DIRECT one (Neon: Connect > turn off 'Connection pooling'; the host has no '-pooler')." >&2; exit 1;;
esac
tables=(amcs fund_categories fund_families schemes external_ids fund_snapshots ingestion_runs data_quality_issues amfi_schemes scheme_mappings nav_coverage scheme_metrics fund_scores backtest_runs)
args=(); for t in "${tables[@]}"; do args+=(-t "$t"); done
# Tables are always schema-qualified: pg_dump's data script empties search_path, and a pooled host (Neon -pooler, Supabase pooler) can hand
# that setting to the next connection, which then cannot find "amcs".
# Safe to re-run: if the destination already holds data the copy is skipped and only the row counts are compared.
if [ "$(psql -tA "$DST" -c "select count(*) from public.amcs")" = "0" ]; then
  # --disable-triggers needs superuser on some hosts; the order above already respects foreign keys, so load in order instead.
  pg_dump --data-only --no-owner "${args[@]}" "$SRC" | psql -v ON_ERROR_STOP=1 "$DST" >/dev/null
else
  echo "destination already has data; skipping the copy and checking row counts"
fi
for t in "${tables[@]}"; do
  a=$(psql -tA "$SRC" -c "select count(*) from public.$t"); b=$(psql -tA "$DST" -c "select count(*) from public.$t")
  [ "$a" = "$b" ] && echo "ok   $t $a" || { echo "MISMATCH $t src=$a dst=$b" >&2; exit 1; }
done
# sequences: keep ids moving forward on the destination
psql -v ON_ERROR_STOP=1 "$DST" -c "select setval(pg_get_serial_sequence('public.schemes','id'), (select max(id) from public.schemes)), setval(pg_get_serial_sequence('public.amcs','id'), (select max(id) from public.amcs))" >/dev/null
