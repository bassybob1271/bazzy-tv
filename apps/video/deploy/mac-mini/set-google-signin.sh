#!/bin/bash
# Turn on "Continue with Google" for the one Bazzy TV login (Bazzy TV, Bazzy Live, BazzyBox).
#   bash <(curl -fsSL https://raw.githubusercontent.com/bassybob1271/bazzy-tv/main/apps/video/deploy/mac-mini/set-google-signin.sh)
# Asks for the Google OAuth client ID and secret (secret typed hidden), saves them in Bazzy TV's .env,
# and restarts the API. Prints no secrets. Backs up .env to .env.bak.
export PATH="/usr/local/bin:/opt/homebrew/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH"
cd "$HOME/Bazzy TV/bazzy-tv/apps/video" || { echo "Can't find ~/Bazzy TV/bazzy-tv/apps/video"; exit 1; }
setv() { if grep -q "^$1=" .env; then sed -i '' "s#^$1=.*#$1=$2#" .env; else printf '%s=%s\n' "$1" "$2" >> .env; fi; }

echo "Google redirect URI to use: https://video.bazzy.tv/api/v1/auth/oauth/google/callback"
read -r -p "Google Client ID: " ID
read -r -s -p "Google Client secret: " SECRET; echo
case "$ID" in *.apps.googleusercontent.com) ;; *) echo "✗ That doesn't look like a Google Client ID (it ends in .apps.googleusercontent.com)."; exit 1 ;; esac
[ -n "$SECRET" ] || { echo "✗ No secret entered."; exit 1; }

cp .env .env.bak
setv GOOGLE_CLIENT_ID "$ID"
setv GOOGLE_CLIENT_SECRET "$SECRET"
grep -q '^PUBLIC_URL=https://video.bazzy.tv' .env || setv PUBLIC_URL https://video.bazzy.tv
echo "✓ Saved. Restarting the Bazzy TV API…"
docker compose -p bazzy-video up -d --force-recreate api >/dev/null 2>&1 || { echo "✗ Couldn't restart the API. Is Docker Desktop running?"; exit 1; }
for i in $(seq 1 45); do curl -sf http://localhost:8000/health >/dev/null && break; sleep 2; done
if curl -sf http://localhost:8000/api/v1/auth/providers | grep -q '"google": *true'; then
  echo "✓ Continue with Google is on. Try it: https://video.bazzy.tv/auth/login"
else
  echo "✗ The API is up but Google isn't switched on yet. Send this to Claude: docker compose -p bazzy-video logs --tail 30 api"
fi
