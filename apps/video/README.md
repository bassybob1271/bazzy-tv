# BAZZY VIDEO

> **Cinema for the Community.** A co-op video distribution platform where 80% of every credit flows to filmmakers.

---

## Stack at a Glance

| Layer | Tech |
|-------|------|
| **Backend API** | FastAPI (Python 3.12) + asyncpg + SQLAlchemy 2 |
| **Database** | PostgreSQL 16 |
| **Cache / Broker** | Redis 7 |
| **Queue** | Celery + Redis; Kafka for event streaming |
| **Transcoding** | FFmpeg — HLS adaptive ladder (4K → 360p) |
| **Storage** | OCI Object Storage (hot) + Backblaze B2 (cold) |
| **CDN / DRM** | Cloudflare Stream — Widevine L1/L3 + FairPlay |
| **Payments** | Stripe Checkout, Stripe Connect, Stripe Tax |
| **Frontend** | Next.js 14 + TypeScript + hls.js + Zustand + Tailwind |
| **Infra** | OCI Compute + Terraform + Nginx |

---

## Credit Economy

```
$10 = 1,000 credits
1 credit = ~1 minute of streaming

Starter  $10   → 1,000 cr
Plus     $25   → 2,750 cr  (+250 bonus)
Pro      $50   → 6,000 cr  (+1,000 bonus)
Cinephile $100 → 13,000 cr (+3,000 bonus)
```

## Payout Waterfall (per credit spent)

```
Gross revenue
  - 3%  payment processing (Stripe)
  - 7%  CDN / delivery
  = 90% net
    → 80% filmmaker  ← the creator's share
    → 10% platform ops
    → 10% reserve pool (co-op cushion)
```

---

## Quick Start

### Prerequisites
- Docker + Docker Compose
- Node 20 (for local frontend dev)
- Python 3.12 (for local backend dev)

### 1. Clone & configure
```bash
git clone https://github.com/bassybob1271/bazzy-video.git
cd bazzy-video
cp .env.example .env
# Edit .env — add Stripe keys, OCI creds, Cloudflare token
```

### 2. Start all services
```bash
docker compose up -d --build
```

Kafka, Zookeeper and Nginx are in the `prod` profile (Kafka isn't wired into the code yet; Nginx needs SSL certs). Include them with `docker compose --profile prod up -d`.

API → http://localhost:8000  
Frontend → http://localhost:3000  
API docs → http://localhost:8000/api/docs

### Demo catalog
On first start with an empty database the API loads 12 demo titles (New Orleans-themed, with sample HLS streams so Play works) and three logins, all with password `bazzydemo`:

| Login | Role |
|-------|------|
| `demo@bazzy.tv` | Viewer with 5,000 credits |
| `filmmaker@bazzy.tv` | Filmmaker who owns the demo titles |
| `admin@bazzy.tv` | Admin |

Set `SEED_DEMO=false` in `.env` for production.

### 3. Local backend dev
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### 4. Local frontend dev
```bash
cd frontend
npm install
npm run dev
```

---

## Sign-in: email, Apple, Google, and "Sign in with Bazzy TV"

**Apple and Google.** The login and sign-up pages show "Continue with Apple" and "Continue with Google" once their keys are in `.env` (see `.env.example`). Both use OpenID Connect with the authorization code flow; Google also uses PKCE. The `id_token` is checked against the provider's published keys, audience, issuer and nonce, and a short-lived HttpOnly cookie ties the return trip to the browser that started it.

Accounts are matched in this order:
1. A Google or Apple account already linked to a user signs straight in.
2. Otherwise, an email the provider has verified joins the user with that email. If that user's email was never verified, their old password stops working, because the provider just proved someone else owns the address.
3. Otherwise, a new viewer account is created.

**Apple setup notes.** Apple only returns over https, and it sends the person's name on the very first sign-in only (it's saved then).

**Sign in with Bazzy TV.** Bazzy TV is an OAuth 2.0 provider for other Bazzy apps, starting with BazzyBox (`bassybob1271/Stowage`), so one account works everywhere, however it was created. It uses the authorization code flow with PKCE, for apps registered in `OAUTH_CLIENTS`:

| Step | Where |
|---|---|
| App sends the browser to | `{PUBLIC_URL}/oauth/authorize?response_type=code&client_id=…&redirect_uri=…&state=…&code_challenge=…&code_challenge_method=S256` |
| User signs in if needed; consent is skipped for `"trusted": true` apps | website page `/oauth/authorize` |
| App's server swaps the code (single use, 5 minutes) | `POST /api/v1/oauth/token` (client secret via Basic auth or form) |
| App reads the user | `GET /api/v1/oauth/userinfo` → `sub`, `email`, `email_verified`, `name`, `picture` |

Redirect URIs must match exactly. Tokens issued to apps carry `typ=oauth_access` and the app's `aud`, so they can't be used as a Bazzy TV session.

Tests: `cd backend && pip install aiosqlite greenlet && pytest` (Google and Apple are faked with local keys).

---

## API Routes

| Group | Base | Description |
|-------|------|-------------|
| Auth | `/api/v1/auth` | Register, login, JWT, Apple/Google sign-in |
| OAuth | `/api/v1/oauth` | Sign in with Bazzy TV (authorize, token, userinfo) |
| Titles | `/api/v1/titles` | Browse, stream, vote |
| Wallet | `/api/v1/wallet` | Credits, Stripe checkout |
| Filmmaker | `/api/v1/filmmaker` | Dashboard, payouts |
| Admin | `/api/v1/admin` | Queue, metrics, ledger |

Full interactive docs at `/api/docs` (Swagger UI) and `/api/redoc`.

---

## Discovery Algorithm

Titles are scored by 5 weighted signals:

| Signal | Weight | Source |
|--------|--------|--------|
| Completion rate | 35% | Streaming heartbeat |
| Fan Unit votes | 20% | 1-5 star ratings |
| Revenue velocity | 20% | Credits earned per week |
| Editorial score | 15% | Curator-assigned 0–1 |
| Social referral | 10% | Referral tracking (future) |

Scores are recomputed nightly by a Celery Beat task.

---

## Content Categories

- 📽️ **Documentary**
- 💕 **Romance**
- 🔍 **Crime**
- 👻 **Horror**
- ⚡ **New Releases**

---

## Infrastructure

OCI Ashburn (primary) + Cloudflare CDN layer.  
Cost vs AWS: **~58% cheaper** per 2-hour stream ($0.685 vs $1.616).

```
OCI Object Storage → Cloudflare CDN → HLS → hls.js player
                                   ↕
                          Widevine / FairPlay DRM
                          Forensic watermark (per session)
```

Deploy with Terraform:
```bash
cd infrastructure/terraform
cp terraform.tfvars.example terraform.tfvars
terraform init && terraform plan && terraform apply
```

---

## Co-op Governance

Bazzy Video is structured as a **Delaware Benefit LLC**.

- **Fan Units** — viewers earn governance weight through watch history; Fan Unit votes influence the discovery algorithm.
- **Filmmaker Units** — filmmakers accumulate units proportional to earnings; participate in platform decisions.
- **Reserve Pool** — 10% of all revenue retained as co-op cushion; distributable by member vote.

---

## License

Proprietary. All rights reserved. © Bazzy Live LLC.
