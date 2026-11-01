#!/usr/bin/env bash
# Package the NAV store and derived artefacts and upload them as a GitHub release asset, so a host with no persistent disk
# (Render free) can download them at build time.  Needs the GitHub CLI (`gh auth login`) and a repo on GitHub.
# Usage: scripts/publish_data.sh [tag]      (default tag: data-latest)
set -euo pipefail
cd "$(dirname "$0")/.."
tag="${1:-data-latest}"
bundle="$(mktemp -d)/qsmf-data.tar.gz"
tar czf "$bundle" data/silver data/gold
echo "bundle: $(du -h "$bundle" | cut -f1)"
sha256sum "$bundle" | cut -d' ' -f1 > "$bundle.sha256"
gh release view "$tag" >/dev/null 2>&1 || gh release create "$tag" --title "Data bundle" --notes "NAV store and derived data. Replaced on each refresh."
gh release upload "$tag" "$bundle" "$bundle.sha256" --clobber
echo "uploaded to release $tag"
