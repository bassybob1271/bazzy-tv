#!/bin/sh
# MediaMTX runOnReady for live/<playback_id>, native on the Mac (MTX_PATH is set by MediaMTX).
# 1. Tell the API the show is on air. 2. Keep the public silent preview running if ffmpeg is here.
curl -fsS -o /dev/null -X POST "${BAZZY_API:-http://127.0.0.1:8000}/api/v1/live/ingest/hook?event=ready&path=${MTX_PATH}&secret=${MEDIAMTX_HOOK_SECRET}"
for f in /opt/homebrew/bin/ffmpeg /usr/local/bin/ffmpeg; do [ -x "$f" ] && FF=$f && break; done
if [ -n "${FF:-}" ]; then
  exec "$FF" -nostdin -loglevel error -i "rtmp://127.0.0.1:1935/${MTX_PATH}" -an \
    -vf "scale=640:480:force_original_aspect_ratio=increase,crop=640:480,fps=15" \
    -c:v libx264 -preset veryfast -tune zerolatency -b:v 800k -maxrate 1000k -bufsize 2000k -g 30 \
    -f flv "rtmp://127.0.0.1:1935/${MTX_PATH}_preview"
fi
# No ffmpeg: stay alive so MediaMTX doesn't rerun this hook in a loop.
exec sleep 86400
