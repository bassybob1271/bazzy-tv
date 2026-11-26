# Roadmap: one platform, three apps

1. ✅ **Monorepo** — Bazzy Video moved to `apps/video` with full history.
2. ⬜ **Import Stowage** — `scripts/import-stowage.sh` splits it with history: BazzyBox → `apps/box`,
   Bazzy Live → `apps/live`, tunnel → `infra/cloudflared`. Then repoint the `io.bazzy.stack` launchd service.
3. ⬜ **Platform service** — Box and Live are separate apps (likely Node), so the platform is a service, not a library:
   pull accounts + "Sign in with Bazzy TV", wallet/credits/Stripe and storage policy out of `apps/video/backend`
   into `platform/api` (its own container and database). Video, Live and Box all call it; each app keeps its own
   content tables. One wallet: credits bought anywhere spend everywhere.
4. ⬜ **Shared UI** — move navbar, player, cards and brand into `packages/ui`; apps import it.
5. ⬜ **Bazzy Live** — start `apps/live` on the platform (sign-in, wallet, `bazzylive` bucket from day one).
6. ⬜ **One deploy** — a single compose / tunnel config in `infra/` that runs all three apps on the Mac mini.
