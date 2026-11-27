#!/bin/sh
# MediaMTX runOnNotReady for live/<playback_id>: the ATEM feed stopped.
wget -q -O /dev/null --post-data= \
  "http://api:8000/api/v1/live/ingest/hook?event=notready&path=${MTX_PATH}&secret=${MEDIAMTX_HOOK_SECRET}"
