#!/bin/bash
# Serve BazzyBox directly on https://box.bazzy.tv (instead of redirecting to box.bazzy.io).
# Run on the Mac mini:
#   curl -fsSL https://raw.githubusercontent.com/bassybob1271/bazzy-tv/main/apps/video/deploy/mac-mini/box-on-bazzy-tv.sh | bash
# box.bazzy.io keeps working too. Nothing is deleted; .env and the tunnel config get a .bak copy.
export PATH="/usr/local/bin:/opt/homebrew/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH"
BOX_DIR=${STOWAGE_DIR:-$HOME/Stowage}
CFG="$HOME/.cloudflared/config-bazzy-tv.yml"
LAUNCHER="$HOME/Bazzy TV/Put Bazzy on bazzy.tv.command"
ok() { printf '\033[1;32m✓\033[0m %s\n' "$*"; }
bad() { printf '\033[1;31m✗\033[0m %s\n' "$*"; }

# 1. BazzyBox must be running on this Mac
if curl -fs -o /dev/null http://127.0.0.1:8787/api/health; then ok "BazzyBox is running on this Mac (port 8787)"
else bad "BazzyBox isn't answering on port 8787. Start it first: launchctl kickstart -k gui/$(id -u)/io.bazzy.stack"; exit 1; fi

# 2. BazzyBox's own address → box.bazzy.tv (sign-in return, share links, Dropbox import)
ENV="$BOX_DIR/.env"
[ -f "$ENV" ] || { bad "Can't find $ENV"; exit 1; }
cp "$ENV" "$ENV.bak"
if grep -q '^APP_ORIGIN=' "$ENV"; then sed -i '' 's#^APP_ORIGIN=.*#APP_ORIGIN=https://box.bazzy.tv#' "$ENV"
else printf 'APP_ORIGIN=https://box.bazzy.tv\n' >> "$ENV"; fi
ok "BazzyBox address set to https://box.bazzy.tv"

# 3. Tunnel: box.bazzy.tv → BazzyBox (was → landing page, which redirected to .io)
point_box() { # file
  awk '{ print } /hostname: box\.bazzy\.tv/ { getline; sub(/http:\/\/host\.docker\.internal:[0-9]+/, "http://host.docker.internal:8787"); print }' "$1" > "$1.new" && mv "$1.new" "$1"
}
[ -f "$CFG" ] || { bad "Can't find $CFG. Run 'Put Bazzy on bazzy.tv' once first."; exit 1; }
cp "$CFG" "$CFG.bak"; point_box "$CFG"
grep -A1 'box.bazzy.tv' "$CFG" | grep -q ':8787' && ok "Tunnel sends box.bazzy.tv to BazzyBox" || { bad "Couldn't update $CFG"; exit 1; }
# Keep the launcher in step, so running it again doesn't undo this.
if [ -f "$LAUNCHER" ]; then
  point_box "$LAUNCHER"; sed -i '' 's#box.bazzy.tv   → forwards to box.bazzy.io for now#box.bazzy.tv   → BazzyBox#' "$LAUNCHER"; chmod +x "$LAUNCHER"
fi

# 4. Restart BazzyBox and the bazzy.tv tunnel
launchctl kickstart -k "gui/$(id -u)/io.bazzy.stack" 2>/dev/null && ok "BazzyBox restarted"
for i in $(seq 1 30); do curl -fs -o /dev/null http://127.0.0.1:8787/api/health && break; sleep 2; done
docker restart bazzy-tv-tunnel >/dev/null && ok "bazzy.tv tunnel restarted" || { bad "Couldn't restart the tunnel. Is Docker Desktop running?"; exit 1; }

# 5. Check from the outside
sleep 10
for i in 1 2 3 4 5 6; do
  code=$(curl -s -o /dev/null -w '%{http_code}' https://box.bazzy.tv/api/health)
  [ "$code" = 200 ] && { ok "https://box.bazzy.tv is BazzyBox"; open https://box.bazzy.tv; exit 0; }
  sleep 5
done
bad "box.bazzy.tv answered $code. Logs: docker logs --tail 30 bazzy-tv-tunnel"
