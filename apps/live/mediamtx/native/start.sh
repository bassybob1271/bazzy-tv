#!/bin/bash
# Bazzy Live ingest, running directly on this Mac (not in Docker).
#
# Docker Desktop on macOS can refuse connections from other devices on a cable, such as an ATEM
# plugged into the Mac, even though everything works from the Mac itself. MediaMTX is one small
# program, so it runs here natively instead and talks to the Bazzy API on localhost:8000.
#
#   bash start.sh     download MediaMTX once, then (re)start it in the background
#   bash start.sh stop
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

stop() { [ -f "$PIDF" ] && kill "$(cat "$PIDF")" 2>/dev/null || true; rm -f "$PIDF"; pkill -f "$BIN/mediamtx " 2>/dev/null || true; }
if [ "${1:-}" = stop ]; then stop; echo "✓ Ingest stopped"; exit 0; fi

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

# Same settings as the Docker config, with this Mac's paths and the API on localhost.
# (macOS sed can't insert lines, so the auth address goes first; paths are quoted for the space in "Bazzy TV")
printf 'authHTTPAddress: http://127.0.0.1:8000/api/v1/live/ingest/auth?secret=%s\n' "$SECRET" > "$BIN/mediamtx.yml"
sed -e "s#recordPath: /recordings/#recordPath: \"$ROOT/recordings/#; /recordPath:/s#\$#\"#" \
    -e "s#sh /hooks/on_ready.sh#sh '$HERE/on_ready.sh'#" \
    -e "s#sh /hooks/on_notready.sh#sh '$HERE/on_notready.sh'#" \
    "$HERE/../mediamtx.yml" >> "$BIN/mediamtx.yml"

stop
cd "$BIN"
MEDIAMTX_HOOK_SECRET="$SECRET" BAZZY_API=http://127.0.0.1:8000 nohup "$BIN/mediamtx" "$BIN/mediamtx.yml" >> "$LOG" 2>&1 &
echo $! > "$PIDF"
sleep 2
if kill -0 "$(cat "$PIDF")" 2>/dev/null && grep -q "RTMP\] listener opened" "$LOG"; then
  IP=$(ipconfig getifaddr en0 2>/dev/null || true)
  echo "✓ Live ingest running on this Mac (RTMP :1935, HLS :8888). Log: Bazzy TV/ingest.log"
  command -v ffmpeg >/dev/null || echo "  (no ffmpeg here: shows stream fine; the silent on-air preview needs 'brew install ffmpeg')"
else
  echo "✗ MediaMTX didn't start:"; tail -20 "$LOG"; exit 1
fi
