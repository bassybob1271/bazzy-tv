# Bazzy TV

**Bazzy TV is the platform. Bazzy Video, Bazzy Live and BazzyBox run on it.**
One account, one wallet and one storage layer, shared by all three.

| App | What it is | Folder | Storage bucket | Status |
|-----|-----------|--------|----------------|--------|
| **Bazzy Video** | Co-op streaming site — rent, buy, filmmakers keep 80% | [`apps/video`](apps/video) | `bazzyvideo` | Working: FastAPI + Next.js + Docker, B2 upload → HLS → playback |
| **Bazzy Live** | Live events and streams | [`apps/live`](apps/live) | `bazzylive` | Running from the `Stowage` repo (`Stowage/apps/live`) — to be imported here |
| **BazzyBox** | No-lock-in file storage for filmmakers and musicians | [`apps/box`](apps/box) | `bazzybox` | Running from the `Stowage` repo (its root) — to be imported here |

## Layout

```
bazzy-tv/
├─ apps/
│  ├─ video/      Bazzy Video (moved here from the bazzy-video repo, full history kept)
│  ├─ live/       Bazzy Live (from Stowage/apps/live)
│  └─ box/        BazzyBox (from the Stowage repo root)
├─ platform/      Shared backend: accounts & sign-in, credits/wallet, Stripe, B2 storage, admin
├─ packages/ui/   Shared look: navbar, player, cards, brand
├─ infra/         Docker, Railway, Cloudflare Tunnel (from Stowage/deploy/cloudflared), Mac mini
├─ scripts/       Repo tooling (e.g. importing Stowage)
└─ docs/
```

## What's shared (and where it lives today)

| Shared piece | Today | Moving to |
|---|---|---|
| Accounts, Sign in with Google/Apple, “Sign in with Bazzy TV” for other apps | `apps/video/backend/app/api/routes/{auth,social,provider}.py`, `core/security.py` | `platform/auth` |
| Credits, wallet, Stripe, payout waterfall | `apps/video/backend/app/services/credit_service.py`, `routes/wallet.py` | `platform/wallet` |
| Backblaze B2 storage (S3 API) | `apps/video/backend/app/services/storage.py` | `platform/storage` (one module, one bucket per app) |
| Admin & review | `apps/video/backend/app/api/routes/admin.py` | `platform/admin` |
| Navbar, player, cards, brand | `apps/video/frontend/src/components` | `packages/ui` |

Bazzy Video's backend is already the platform's account service: Bazzy Live and BazzyBox sign in through it
("Sign in with Bazzy TV", OAuth 2.0 + PKCE). Box and Live look like Node/Next.js apps, so the platform is shared as a
**service they call**, not a library they import. See [docs/ROADMAP.md](docs/ROADMAP.md).

## Working on it

Keep your copy **outside iCloud-synced folders** (Desktop / Documents) — iCloud corrupts git's files.

```bash
mkdir -p ~/Developer && cd ~/Developer
git clone https://github.com/bassybob1271/bazzy-tv.git
cd bazzy-tv/apps/video && cp .env.example .env   # add your keys
docker compose up -d --build                      # site: http://localhost:3000
```

Mac mini (production): see [infra/README.md](infra/README.md).

## License

Proprietary. All rights reserved. © Bazzy Live LLC.
