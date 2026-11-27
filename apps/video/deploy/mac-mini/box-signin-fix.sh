#!/bin/bash
# Turn on "Sign in with Bazzy TV" in BazzyBox on this Mac, and make sure only Bazzy TV's ingest runs.
#   curl -fsSL https://raw.githubusercontent.com/bassybob1271/bazzy-tv/main/apps/video/deploy/mac-mini/box-signin-fix.sh | bash
# Prints no secrets. Backs up ~/Stowage/.env to .env.bak first.
BOX_ENV="${STOWAGE_DIR:-$HOME/Stowage}/.env"
TV_ENV="$HOME/Bazzy TV/bazzy-tv/apps/video/.env"
INGEST="$HOME/Bazzy TV/bazzy-tv/apps/live/mediamtx/native/start.sh"
ok() { printf '\033[1;32m✓\033[0m %s\n' "$*"; }
bad() { printf '\033[1;31m✗\033[0m %s\n' "$*"; }
setv() { if grep -q "^$1=" "$BOX_ENV"; then sed -i '' "s#^$1=.*#$1=$2#" "$BOX_ENV"; else printf '%s=%s\n' "$1" "$2" >> "$BOX_ENV"; fi; }

[ -f "$BOX_ENV" ] || { bad "Can't find $BOX_ENV"; exit 1; }
[ -f "$TV_ENV" ] || { bad "Can't find $TV_ENV"; exit 1; }

# 1. BazzyBox's client secret, as Bazzy TV knows it (OAUTH_CLIENTS → client_id "bazzybox")
SECRET=$(grep '^OAUTH_CLIENTS=' "$TV_ENV" | tr -d '\\' | grep -o '"client_id": *"bazzybox"[^}]*' | grep -o '"client_secret": *"[^"]*"' | sed 's/.*"client_secret": *"//; s/"$//')
[ -n "$SECRET" ] || { bad "Bazzy TV has no 'bazzybox' sign-in client in its .env (OAUTH_CLIENTS). Send this to Claude."; exit 1; }
cp "$BOX_ENV" "$BOX_ENV.bak"
setv BAZZY_AUTH_URL https://video.bazzy.tv
setv BAZZY_CLIENT_ID bazzybox
setv BAZZY_CLIENT_SECRET "$SECRET"
ok "BazzyBox will sign members in with their Bazzy TV account"

# 2. Bazzy TV's ingest must be installed, so the old Live service leaves the ATEM's port alone
if [ ! -f "$HOME/Library/LaunchAgents/tv.bazzy.ingest.plist" ]; then
  bash "$INGEST" install && ok "Bazzy TV ingest installed as a login item"
else
  ok "Bazzy TV ingest is a login item"
fi
git -C "${STOWAGE_DIR:-$HOME/Stowage}" pull -q --ff-only 2>/dev/null
grep -q tv.bazzy.ingest "${STOWAGE_DIR:-$HOME/Stowage}/apps/live/scripts/run-native.sh" && ok "Old Live service will step aside" || bad "BazzyBox code is out of date: cd ~/Stowage && git pull"

# 3. Restart BazzyBox (and the old service, without its ingest)
launchctl kickstart -k "gui/$(id -u)/io.bazzy.stack" && ok "BazzyBox restarted"
for i in $(seq 1 30); do curl -fs -o /dev/null http://127.0.0.1:8787/api/health && break; sleep 2; done
if curl -fs http://127.0.0.1:8787/api/auth/session | grep -q '"bazzy":true'; then ok "Sign in with Bazzy TV is on: open https://box.bazzy.tv"
else bad "BazzyBox is up but Bazzy sign-in is still off. Logs: tail -20 ~/Library/Logs/bazzy.log"; fi
sleep 3
P=$(lsof -tiTCP:1935 -sTCP:LISTEN | head -1)
ps -o command= -p "$P" 2>/dev/null | grep -q "mediamtx-native" && ok "ATEM port held by Bazzy TV's ingest" || bad "ATEM port: $(ps -o command= -p "$P" 2>/dev/null)"
