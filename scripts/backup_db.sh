#!/usr/bin/env bash
# Dump the Postgres database to a timestamped, compressed file. Run from cron/a scheduler; copy the file off-host.
# Usage: QSMF_PG_URL=postgresql://user:pass@host:5432/qsmf scripts/backup_db.sh [outdir]
set -euo pipefail
out="${1:-backups}"; mkdir -p "$out"
f="$out/qsmf-$(date -u +%Y%m%dT%H%M%SZ).sql.gz"
pg_dump --no-owner "${QSMF_PG_URL:?set QSMF_PG_URL}" | gzip > "$f"
gzip -t "$f" && echo "ok $f ($(du -h "$f" | cut -f1))"
find "$out" -name 'qsmf-*.sql.gz' -mtime +14 -delete   # keep 14 days locally
