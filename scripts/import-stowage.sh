#!/bin/bash
# Import the Stowage repo (BazzyBox) into apps/box, keeping its full history.
# Needs: git and git-filter-repo (pip install git-filter-repo). Run from the repo root.
set -euo pipefail
cd "$(dirname "$0")/.."
SRC=${1:-https://github.com/bassybob1271/Stowage.git}
TMP=$(mktemp -d)
git clone "$SRC" "$TMP/stowage"
( cd "$TMP/stowage" && git filter-repo --force --to-subdirectory-filter apps/box )
BRANCH=$(git -C "$TMP/stowage" symbolic-ref --short HEAD)
git remote add stowage-import "$TMP/stowage"
git fetch stowage-import "$BRANCH"
git merge --allow-unrelated-histories -m "Import BazzyBox (Stowage) into apps/box with history" "stowage-import/$BRANCH" -X theirs
git remote remove stowage-import
echo "✓ BazzyBox imported into apps/box"
