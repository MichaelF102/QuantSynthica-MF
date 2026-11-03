#!/usr/bin/env bash
# Download the data bundle into ./data at build time.
# On Render the URL is worked out for you from the repository (RENDER_GIT_REPO_SLUG), so nothing needs configuring for a public repo.
# Override with QSMF_DATA_URL. A private repo also needs QSMF_GITHUB_TOKEN. An integrity check runs when "<URL>.sha256" exists.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -z "${QSMF_DATA_URL:-}" ] && [ -n "${RENDER_GIT_REPO_SLUG:-}" ]; then
  QSMF_DATA_URL="https://github.com/${RENDER_GIT_REPO_SLUG}/releases/download/data-latest/qsmf-data.tar.gz"
fi
: "${QSMF_DATA_URL:?set QSMF_DATA_URL to the data bundle URL (a GitHub release asset)}"
auth=(); [ -n "${QSMF_GITHUB_TOKEN:-}" ] && auth=(-H "Authorization: Bearer $QSMF_GITHUB_TOKEN" -H "Accept: application/octet-stream")
tmp="$(mktemp)"
curl -fsSL "${auth[@]}" "$QSMF_DATA_URL" -o "$tmp"
want="${QSMF_DATA_SHA256:-}"
[ -n "$want" ] || want="$(curl -fsSL "${auth[@]}" "${QSMF_DATA_SHA256_URL:-$QSMF_DATA_URL.sha256}" 2>/dev/null | cut -d' ' -f1 || true)"
if [ -n "$want" ]; then
  got="$(sha256sum "$tmp" | cut -d' ' -f1)"
  [ "$want" = "$got" ] || { echo "checksum mismatch: wanted $want got $got" >&2; exit 1; }
  echo "checksum ok"
fi
tar xzf "$tmp" -C .
rm -f "$tmp"
echo "data ready: $(du -sh data/silver data/gold | tr '\n' ' ')"
