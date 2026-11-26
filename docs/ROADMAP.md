# Roadmap: one platform, three apps

1. ✅ **Monorepo** — Bazzy Video moved to `apps/video` with full history.
2. ⬜ **Import BazzyBox** — run `scripts/import-stowage.sh` (Stowage → `apps/box`, history kept).
3. ⬜ **Extract the platform** — move auth, wallet, storage and admin from `apps/video/backend` into `platform/`
   as an installable Python package; Bazzy Video imports it instead of owning it. One database for accounts and
   credits; each app keeps its own tables.
4. ⬜ **Shared UI** — move navbar, player, cards and brand into `packages/ui`; apps import it.
5. ⬜ **Bazzy Live** — start `apps/live` on the platform (sign-in, wallet, `bazzylive` bucket from day one).
6. ⬜ **One deploy** — a single compose / tunnel config in `infra/` that runs all three apps on the Mac mini.
