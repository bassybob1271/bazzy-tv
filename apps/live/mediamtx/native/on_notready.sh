#!/bin/sh
# MediaMTX runOnNotReady for live/<playback_id>: the ATEM feed stopped.
curl -fsS -o /dev/null -X POST "${BAZZY_API:-http://127.0.0.1:8000}/api/v1/live/ingest/hook?event=notready&path=${MTX_PATH}&secret=${MEDIAMTX_HOOK_SECRET}"
