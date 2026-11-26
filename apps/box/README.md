# BazzyBox

No-lock-in file storage for filmmakers and musicians — a cheaper Dropbox alternative that runs inside Bazzy TV.

The code currently lives at the root of the **`bassybob1271/Stowage`** repo. `scripts/import-stowage.sh` moves it
here with its full history (and Bazzy Live to `apps/live`, the tunnel config to `infra/cloudflared`).

- Sign-in: "Sign in with Bazzy TV" (client `bazzybox`, callback `https://box.bazzy.io/api/auth/bazzy/callback`)
- Storage: Backblaze B2 bucket `bazzybox`
- Public URL: https://box.bazzy.io
