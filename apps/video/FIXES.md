# Fixes applied (Nov 24, 2026)

Ran the full stack locally (Postgres 16 + API + Next.js production build) and browser-tested every page as viewer, filmmaker and admin.

## Backend
- `requirements.txt`: `cloudflare==3.3.0` doesn't exist → 3.1.1; pinned `httpx` 0.27.2 and `pydantic` 2.9.2 to resolve conflicts; added `email-validator` (via `pydantic[email]`) and `bcrypt==4.0.1` (passlib compat).
- `models.py`: `CreditTransaction.metadata` is reserved by SQLAlchemy (crashed on startup) → attribute renamed `extra_data` (DB column still `metadata`).
- `models.py`: `User.filmmaker_profile` now eager-loads — every filmmaker endpoint was returning 500.
- `auth.py`: filmmaker `bio` from signup is now saved.
- `transcode_worker.py`: tasks now go to the `default` queue the worker actually listens on.

## Frontend
- Added missing `next.config.js` (standalone output for Docker), `tsconfig.json` (`@/` imports), `postcss.config.js`, `package-lock.json`.
- `eslint` 9 → 8 (required by `eslint-config-next` 14).
- Discover page syntax error (nested quotes) fixed.
- 59 type errors: pages were using field names the API doesn't return (wallet balance, tiers, filmmaker dashboard, payouts, admin metrics, watch page player). All aligned to the real API.
- Nav category links pointed to `/browse/*` pages that don't exist → now open Discover filtered by category.
- Logged-in users were bounced to login on refresh of Wallet/Filmmaker/Admin → pages now wait for the saved session.
- Stripe Connect button now runs the real OAuth redirect (needs `STRIPE_CONNECT_CLIENT_ID` in `.env`).

## Docker / config
- `NEXT_PUBLIC_API_URL` was missing `/api/v1` → every API call would 404.
- Kafka, Zookeeper and Nginx moved to a `prod` profile (Kafka isn't used by the code yet; Nginx needs SSL certs).
- `.env` created from `.env.example` with a random `SECRET_KEY`.
- README: API docs are at `/api/docs`.
