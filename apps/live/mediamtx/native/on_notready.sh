#!/bin/sh
# MediaMTX runOnNotReady for live/<playback_id>: the ATEM feed stopped. Filled in by start.sh.
API="@API@"; SECRET="@SECRET@"; LOG="@LOG@"
curl -fsS -o /dev/null -X POST "$API/api/v1/live/ingest/hook?event=notready&path=${MTX_PATH}&secret=$SECRET" 2>>"$LOG" \
  && echo "$(date '+%Y/%m/%d %H:%M:%S') INF hook: ${MTX_PATH} feed stopped" >> "$LOG"
