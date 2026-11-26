# Platform (shared backend)

Shared services used by every Bazzy TV app. Being extracted from `apps/video/backend` — see the table in the
root README and [docs/ROADMAP.md](../docs/ROADMAP.md).

Planned modules:

- `auth/` — accounts, sessions, Google/Apple sign-in, "Sign in with Bazzy TV" (OAuth provider for the other apps)
- `wallet/` — credits, Stripe Checkout/Connect, payout waterfall (80% to creators)
- `storage/` — Backblaze B2 client: upload, presigned links, CDN URLs, CORS, health — one bucket per app
- `admin/` — review queue, metrics, ledger
