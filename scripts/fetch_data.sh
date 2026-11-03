#!/usr/bin/env bash
# Download the data bundle into ./data at build time.
# On Render the URL is worked out for you from the repository (RENDER_GIT_REPO_SLUG), so nothing needs configuring for a public repo.
# Override with QSMF_DATA_URL. A private repo also needs QSMF_GITHUB_TOKEN (fine-grained, Contents: read-only; resolved through the GitHub API). An integrity check runs when "<URL>.sha256" exists.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -z "${QSMF_DATA_URL:-}" ] && [ -n "${RENDER_GIT_REPO_SLUG:-}" ]; then
  QSMF_DATA_URL="https://github.com/${RENDER_GIT_REPO_SLUG}/releases/download/data-latest/qsmf-data.tar.gz"
fi
: "${QSMF_DATA_URL:?set QSMF_DATA_URL to the data bundle URL (a GitHub release asset)}"
# Private repo: a plain release link answers 404 even with a token, so ask the GitHub API for the asset and download that.
get() {  # get <release-asset-url> <output-file>
  local url="$1" out="$2"
  if [ -z "${QSMF_GITHUB_TOKEN:-}" ]; then curl -fsSL "$url" -o "$out"; return; fi
  local slug tag name api
  slug="$(echo "$url" | sed -E 's#https://github.com/([^/]+/[^/]+)/releases/download/.*#\1#')"
  tag="$(echo "$url" | sed -E 's#.*/releases/download/([^/]+)/.*#\1#')"
  name="$(basename "$url")"
  api="$(curl -fsSL -H "Authorization: Bearer $QSMF_GITHUB_TOKEN" -H "Accept: application/vnd.github+json" "https://api.github.com/repos/$slug/releases/tags/$tag" \
    | python3 -c "import json,sys;n=sys.argv[1];print(next(a['url'] for a in json.load(sys.stdin)['assets'] if a['name']==n))" "$name")"
  curl -fsSL -H "Authorization: Bearer $QSMF_GITHUB_TOKEN" -H "Accept: application/octet-stream" "$api" -o "$out"
}
tmp="$(mktemp)"
get "$QSMF_DATA_URL" "$tmp"
want="${QSMF_DATA_SHA256:-}"
if [ -z "$want" ]; then
  sumfile="$(mktemp)"
  if get "${QSMF_DATA_SHA256_URL:-$QSMF_DATA_URL.sha256}" "$sumfile" 2>/dev/null; then want="$(cut -d' ' -f1 "$sumfile")"; fi
fi
if [ -n "$want" ]; then
  got="$(sha256sum "$tmp" | cut -d' ' -f1)"
  [ "$want" = "$got" ] || { echo "checksum mismatch: wanted $want got $got" >&2; exit 1; }
  echo "checksum ok"
fi
tar xzf "$tmp" -C .
rm -f "$tmp"
echo "data ready: $(du -sh data/silver data/gold | tr '\n' ' ')"
