#!/bin/sh
# MediaMTX runOnReady for live/<playback_id>, native on the Mac (MTX_PATH is set by MediaMTX).
# start.sh copies this next to the MediaMTX binary with @API@, @SECRET@ and @LOG@ filled in:
# MediaMTX doesn't pass our own environment through to hooks, so nothing here relies on it.
# 1. Tell the API the show is on air (retried, logged). 2. Keep the silent preview going if ffmpeg is here.
API="@API@"; SECRET="@SECRET@"; LOG="@LOG@"
i=0
until curl -fsS -o /dev/null -X POST "$API/api/v1/live/ingest/hook?event=ready&path=${MTX_PATH}&secret=$SECRET" 2>>"$LOG"; do
  i=$((i+1)); [ $i -ge 5 ] && { echo "$(date '+%Y/%m/%d %H:%M:%S') ERR hook: couldn't tell Bazzy ${MTX_PATH} is on air" >> "$LOG"; break; }
  sleep 2
done
[ $i -lt 5 ] && echo "$(date '+%Y/%m/%d %H:%M:%S') INF hook: ${MTX_PATH} is ON AIR in Bazzy" >> "$LOG"
for f in /opt/homebrew/bin/ffmpeg /usr/local/bin/ffmpeg; do [ -x "$f" ] && FF=$f && break; done
if [ -n "${FF:-}" ]; then
  exec "$FF" -nostdin -loglevel error -i "rtmp://127.0.0.1:1935/${MTX_PATH}" -an \
    -vf "scale=640:480:force_original_aspect_ratio=increase,crop=640:480,fps=15" \
    -c:v libx264 -preset veryfast -tune zerolatency -b:v 800k -maxrate 1000k -bufsize 2000k -g 30 \
    -f flv "rtmp://127.0.0.1:1935/${MTX_PATH}_preview"
fi
# No ffmpeg: stay alive so MediaMTX doesn't rerun this hook in a loop.
exec sleep 86400
