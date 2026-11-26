# Infrastructure

| Where | How | Files |
|---|---|---|
| **Mac mini (production)** | Docker Desktop + Cloudflare Tunnel; bazzyvideo.com, Bazzy Live and BazzyBox share the tunnel | `apps/video/deploy/mac-mini/start.sh` |
| **Local dev** | `docker compose up -d --build` in `apps/video` | `apps/video/docker-compose.yml` |
| **Railway (optional)** | API and web as two services. Set each service's **Root Directory** to `apps/video/backend` and `apps/video/frontend` | `apps/video/**/railway.toml` |

## Mac mini

```bash
cd ~/Developer && git clone https://github.com/bassybob1271/bazzy-tv.git
bash ~/Developer/bazzy-tv/apps/video/deploy/mac-mini/start.sh
```

The script asks for the Backblaze key for the `bazzyvideo` bucket on first run, links "Sign in with Bazzy TV"
into BazzyBox and Bazzy Live, and adds bazzyvideo.com to the Cloudflare Tunnel.

It finds BazzyBox, Bazzy Live and the tunnel config in this repo (`apps/box`, `apps/live`, `infra/cloudflared`)
once Stowage is imported; until then it uses `~/Stowage` (override with `STOWAGE_DIR`).

The tunnel, BazzyBox and Bazzy Live run under the launchd service `io.bazzy.stack`, set up from Stowage. After the
import, point that service at `~/Developer/bazzy-tv` (its plist still references `~/Stowage`).

## Storage

Backblaze B2, one bucket per app: `bazzyvideo`, `bazzylive`, `bazzybox`. Use a separate application key per bucket.
Bunny CDN pull zones can sit in front (free B2 → Bunny egress); set `B2_PUBLIC_URL` to use one.
