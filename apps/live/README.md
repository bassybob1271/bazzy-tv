# Bazzy Live

Concerts and live shows from Greenhouse BK and beyond, at **live.bazzy.tv**.

Bazzy Live runs on the **same backend as Bazzy TV** (`apps/video/backend`): one account, one wallet,
one set of creator earnings and split sheets. A show is a title with a `live_state`; it never appears
in the film catalog, and films never appear here.

| Folder | What |
|---|---|
| `web/` | The Bazzy Live website (Next.js): poster slider, on-air previews, player, artist dashboard |
| `mediamtx/` | MediaMTX config + hooks: the ATEM's RTMP feed in, HLS out, every publish/read checked by the API |

Both run from `apps/video/docker-compose.yml` (services `live-web` on :3001 and `mediamtx` on :1935/:8888).

## How a show works

```
ATEM switcher ──RTMP──▶ MediaMTX ──HLS──▶ live.bazzy.tv player
 (at the venue)          checks the stream key and each viewer's pass with the API
```

1. Any member schedules a show (Artist dashboard → Schedule livestream). Their first show gives them a
   creator profile: earnings, payouts, splits. It doesn't grant film uploads on Bazzy TV.
2. An admin approves it; the poster goes on the slider. Tickets are 200 credits (30 days of replay
   included), joining mid-show is 100, both from the shared Bazzy wallet.
3. Each ticket pays the creator share (3% + 7% fees, then 80%), the same as a film. If the band made a
   split sheet for the show (Bazzy TV → Splits → a live show, show id = the title id), the share is
   divided across the venue, producers, crew… automatically.
4. ATEM setup gives the RTMP server, stream key and a Streaming.xml. ON AIR flips the show to LIVE NOW.
5. The artist ends the show; it moves to Previous Livestreams.

Sign in with Google/Apple runs on Bazzy TV (the address registered with them) with `site=live`, and
returns to `live.bazzy.tv/auth/callback`.

## Streaming engine (Stowage)

The older Node streaming engine is still in `bassybob1271/Stowage` under `apps/live`; MediaMTX replaced
it for ingest here. `scripts/import-stowage.sh` can still bring its history in if it's needed.
