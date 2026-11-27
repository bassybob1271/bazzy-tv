#!/bin/sh
# MediaMTX runOnReady for live/<playback_id> (MTX_PATH is set by MediaMTX).
# 1. Tell the API the show is on air.
# 2. Keep a silent, low-res 4:3 public preview running at live/<playback_id>_preview.
#    MediaMTX stops it when the feed stops (and restarts it if it dies).
wget -q -O /dev/null --post-data= \
  "http://api:8000/api/v1/live/ingest/hook?event=ready&path=${MTX_PATH}&secret=${MEDIAMTX_HOOK_SECRET}"

exec ffmpeg -nostdin -loglevel error \
  -i "rtmp://127.0.0.1:1935/${MTX_PATH}" \
  -an \
  -vf "scale=640:480:force_original_aspect_ratio=increase,crop=640:480,fps=15" \
  -c:v libx264 -preset veryfast -tune zerolatency \
  -b:v 800k -maxrate 1000k -bufsize 2000k -g 30 \
  -f flv "rtmp://127.0.0.1:1935/${MTX_PATH}_preview"
