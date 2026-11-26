#!/bin/bash
# Import the Stowage repo into this monorepo with its full history, split by app:
#   Stowage/ (BazzyBox)           → apps/box/
#   Stowage/apps/live/            → apps/live/
#   Stowage/deploy/cloudflared/   → infra/cloudflared/
# Needs git and git-filter-repo (pip3 install git-filter-repo). Run from anywhere inside the repo.
#   scripts/import-stowage.sh            # from GitHub
#   scripts/import-stowage.sh ~/Stowage  # from a local clone
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
[ -z "$(git status --porcelain)" ] || { echo "Commit or stash your changes first."; exit 1; }
command -v git-filter-repo >/dev/null || { echo "Install git-filter-repo: pip3 install git-filter-repo"; exit 1; }

SRC=${1:-https://github.com/bassybob1271/Stowage.git}
TMP=$(mktemp -d)
git clone --no-local "$SRC" "$TMP/stowage"
cd "$TMP/stowage"
BRANCH=$(git symbolic-ref --short HEAD)
echo "Stowage top level:"; ls -1 | sed 's/^/  /'

git filter-repo --force --to-subdirectory-filter apps/box
git filter-repo --force \
  --path-rename apps/box/apps/live/:apps/live/ \
  --path-rename apps/box/deploy/cloudflared/:infra/cloudflared/
echo "After the split:"; find . -maxdepth 2 -not -path './.git*' -type d | sort | sed 's/^/  /'

cd - >/dev/null
git remote add stowage-import "$TMP/stowage"
git fetch -q stowage-import "$BRANCH"
# Placeholders in apps/box and apps/live give way to the real apps.
git merge --allow-unrelated-histories -X theirs --no-edit \
  -m "Import BazzyBox, Bazzy Live and the tunnel config from Stowage (history kept)" "stowage-import/$BRANCH"
git remote remove stowage-import
rm -rf "$TMP"
echo "✓ Imported. Check apps/box, apps/live and infra/cloudflared, then git push."
