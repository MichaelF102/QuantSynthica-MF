#!/usr/bin/env bash
# Download the data bundle into ./data at build time. Set QSMF_DATA_URL to the release asset URL (public repo) or use a token:
#   QSMF_DATA_URL=https://github.com/OWNER/REPO/releases/download/data-latest/qsmf-data.tar.gz
#   QSMF_GITHUB_TOKEN=...   (private repos only; needs read access to releases)
set -euo pipefail
cd "$(dirname "$0")/.."
: "${QSMF_DATA_URL:?set QSMF_DATA_URL to the data bundle URL}"
tmp="$(mktemp)"
if [ -n "${QSMF_GITHUB_TOKEN:-}" ]; then
  # private repo: resolve the asset (for private repos the API asset URL is needed)
  curl -fsSL -H "Authorization: Bearer $QSMF_GITHUB_TOKEN" -H "Accept: application/octet-stream" "$QSMF_DATA_URL" -o "$tmp"
else
  curl -fsSL "$QSMF_DATA_URL" -o "$tmp"
fi
if [ -n "${QSMF_DATA_SHA256_URL:-}" ]; then
  want="$(curl -fsSL "$QSMF_DATA_SHA256_URL")"; got="$(sha256sum "$tmp" | cut -d' ' -f1)"
  [ "$want" = "$got" ] || { echo "checksum mismatch: wanted $want got $got" >&2; exit 1; }
fi
tar xzf "$tmp" -C .
rm -f "$tmp"
echo "data ready: $(du -sh data/silver data/gold | tr '\n' ' ')"
