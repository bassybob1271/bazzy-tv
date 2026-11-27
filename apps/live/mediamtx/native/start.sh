#!/bin/bash
# Bazzy Live ingest, running directly on this Mac (not in Docker).
#
# Docker Desktop on macOS can refuse connections from other devices on a cable, such as an ATEM
# plugged into the Mac, even though everything works from the Mac itself. MediaMTX is one small
# program, so it runs here natively instead and talks to the Bazzy API on localhost:8000.
#
#   bash start.sh            download MediaMTX once, then (re)start it
#   bash start.sh install    start it at every login and restart it if it ever stops (launchd)
#   bash start.sh uninstall  undo install
#   bash start.sh stop       stop it (an installed one comes back at the next login)
#
# Log: ~/Bazzy TV/ingest.log   Recordings: ~/Bazzy TV/recordings/
set -euo pipefail
VERSION=v1.9.3
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../../../.." && pwd)"            # bazzy-tv
ROOT="$(cd "$REPO/.." && pwd)"                      # Bazzy TV
ENVF="$REPO/apps/video/.env"
BIN="$ROOT/mediamtx-native"
LOG="$ROOT/ingest.log"
PIDF="$BIN/mediamtx.pid"
export PATH="/usr/local/bin:/opt/homebrew/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH"

LABEL=tv.bazzy.ingest
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
DOMAIN="gui/$(id -u)"
installed() { [ -f "$PLIST" ]; }
stop() {
  launchctl bootout "$DOMAIN/$LABEL" >/dev/null 2>&1 || true
  [ -f "$PIDF" ] && kill "$(cat "$PIDF")" 2>/dev/null || true; rm -f "$PIDF"
  pkill -f "$BIN/mediamtx " 2>/dev/null || true
}
MODE="${1:-start}"
case "$MODE" in
  stop) stop; echo "✓ Ingest stopped"; exit 0 ;;
  uninstall) stop; rm -f "$PLIST"; echo "✓ Ingest no longer starts at login"; exit 0 ;;
esac

# The Docker copy would hold port 1935; this one replaces it.
docker rm -f bazzy-video-mediamtx-1 >/dev/null 2>&1 || true

mkdir -p "$BIN" "$ROOT/recordings"
if [ ! -x "$BIN/mediamtx" ]; then
  case "$(uname -m)" in arm64) A=arm64 ;; *) A=amd64 ;; esac
  echo "… downloading MediaMTX $VERSION ($A)"
  curl -fsSL "https://github.com/bluenviron/mediamtx/releases/download/$VERSION/mediamtx_${VERSION}_darwin_${A}.tar.gz" | tar -xz -C "$BIN" mediamtx
  chmod +x "$BIN/mediamtx"
fi

SECRET=$(grep -E '^MEDIAMTX_HOOK_SECRET=' "$ENVF" | head -1 | cut -d= -f2- | tr -d ' "')
[ -n "$SECRET" ] || { echo "✗ MEDIAMTX_HOOK_SECRET is empty in $ENVF"; exit 1; }

# Hooks with the API address, secret and log path written in (MediaMTX doesn't pass our env to hooks).
for h in on_ready on_notready; do
  sed -e "s#@API@#http://127.0.0.1:8000#" -e "s#@SECRET@#$SECRET#" -e "s#@LOG@#$LOG#" "$HERE/$h.sh" > "$BIN/$h.sh"
  chmod 700 "$BIN/$h.sh"
done

# Same settings as the Docker config, with this Mac's paths and the API on localhost.
# (macOS sed can't insert lines, so the auth address goes first; paths are quoted for the space in "Bazzy TV")
printf 'authHTTPAddress: http://127.0.0.1:8000/api/v1/live/ingest/auth?secret=%s\n' "$SECRET" > "$BIN/mediamtx.yml"
sed -e "s#recordPath: /recordings/#recordPath: \"$ROOT/recordings/#; /recordPath:/s#\$#\"#" \
    -e "s#sh /hooks/on_ready.sh#sh '$BIN/on_ready.sh'#" \
    -e "s#sh /hooks/on_notready.sh#sh '$BIN/on_notready.sh'#" \
    "$HERE/../mediamtx.yml" >> "$BIN/mediamtx.yml"

cd "$BIN"

# launchd runs this in the foreground; it restarts MediaMTX if it ever exits.
if [ "$MODE" = run ]; then
  echo "$(date '+%Y/%m/%d %H:%M:%S') INF launcher: starting MediaMTX" >> "$LOG"
  exec "$BIN/mediamtx" "$BIN/mediamtx.yml" >> "$LOG" 2>&1
fi

if [ "$MODE" = install ]; then
  mkdir -p "$(dirname "$PLIST")"
  cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array><string>/bin/bash</string><string>$HERE/start.sh</string><string>run</string></array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>10</integer>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
</dict></plist>
PL
fi

stop
if installed; then
  launchctl bootstrap "$DOMAIN" "$PLIST"
else
  nohup "$BIN/mediamtx" "$BIN/mediamtx.yml" >> "$LOG" 2>&1 &
  echo $! > "$PIDF"
fi
for i in 1 2 3 4 5 6; do sleep 1; pgrep -f "$BIN/mediamtx " >/dev/null && lsof -nP -iTCP:1935 -sTCP:LISTEN >/dev/null 2>&1 && break; done
if pgrep -f "$BIN/mediamtx " >/dev/null && lsof -nP -iTCP:1935 -sTCP:LISTEN >/dev/null 2>&1; then
  installed && echo "✓ Starts by itself at every login, and restarts if it ever stops"
  IP=$(ipconfig getifaddr en0 2>/dev/null || true)
  echo "✓ Live ingest running on this Mac (RTMP :1935, HLS :8888). Log: Bazzy TV/ingest.log"
  command -v ffmpeg >/dev/null || echo "  (no ffmpeg here: shows stream fine; the silent on-air preview needs 'brew install ffmpeg')"
else
  echo "✗ MediaMTX didn't start:"; tail -20 "$LOG"; exit 1
fi
