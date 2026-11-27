#!/bin/bash
# Run Bazzy TV on the Bazzy Mac mini (Docker Desktop) and publish it at https://bazzyvideo.com
# through the same Cloudflare Tunnel as Bazzy Live and BazzyBox.
#
#   bash ~/Developer/bazzy-tv/apps/video/deploy/mac-mini/start.sh
#
# Finds BazzyBox, Bazzy Live and the tunnel config in the bazzy-tv monorepo
# (apps/box, apps/live, infra/cloudflared) once Stowage is imported; until then in ~/Stowage
# (override with STOWAGE_DIR).
#
# First run: creates .env with fresh secrets, asks for a Backblaze key for the bazzyvideo bucket,
# turns on "Sign in with Bazzy TV" in BazzyBox and Bazzy Live, builds and starts everything.
# Later runs: rebuild + restart (keeps .env and the database).
set -euo pipefail
cd "$(dirname "$0")/../.."
HOST=${TV_HOST:-bazzyvideo.com}
ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
if [ -z "${STOWAGE_DIR:-}" ] && [ -n "$ROOT" ] && [ -f "$ROOT/infra/cloudflared/native.yml" ]; then
  BOX_DIR="$ROOT/apps/box"; LIVE_DIR="$ROOT/apps/live"; TUNNEL_YML="$ROOT/infra/cloudflared/native.yml"
else
  STOWAGE=${STOWAGE_DIR:-$HOME/Stowage}
  BOX_DIR="$STOWAGE"; LIVE_DIR="$STOWAGE/apps/live"; TUNNEL_YML="$STOWAGE/deploy/cloudflared/native.yml"
fi
say() { printf '\n\033[1;34m▸\033[0m %s\n' "$*"; }
rnd() { openssl rand -hex "${1:-32}"; }
set_var() { # file, name, value — replace or append NAME=value
  [ -f "$1" ] || return 0
  if grep -q "^$2=" "$1"; then
    awk -v n="$2" -v v="$3" 'BEGIN{FS=OFS="="} $1==n {print n "=" v; next} {print}' "$1" > "$1.tmp" && mv "$1.tmp" "$1"
  else printf '%s=%s\n' "$2" "$3" >> "$1"; fi
  chmod 600 "$1"
}

command -v docker >/dev/null || { echo "Install Docker Desktop first (docker.com), open it once, then rerun."; exit 1; }
docker info >/dev/null 2>&1 || { open -a Docker; echo "Starting Docker Desktop…"; until docker info >/dev/null 2>&1; do sleep 3; done; }

if [ ! -f .env ]; then
  say "Settings (.env)"
  echo "Backblaze: Application Keys → Add a New Application Key (NOT the master key)."
  echo "Bucket: bazzyvideo (or All buckets), Read and Write, File name prefix EMPTY."
  read -r -p "B2 endpoint (bucket page, e.g. s3.us-east-005.backblazeb2.com): " EP </dev/tty
  EP=${EP#https://}; EP="https://${EP%/}"
  while :; do
    read -r -p "keyID: " KID </dev/tty; read -r -s -p "applicationKey (hidden): " KEY </dev/tty; echo
    KID=$(printf '%s' "$KID" | tr -d ' "\r\n'); KEY=$(printf '%s' "$KEY" | tr -d ' "\r\n')
    curl -s -u "$KID:$KEY" https://api.backblazeb2.com/b2api/v3/b2_authorize_account | grep -q accountId && break
    echo "❌ Backblaze rejected that pair, try again."
  done
  BOX_SECRET=$(rnd); LIVE_SECRET=$(rnd); PG=$(rnd 16)
  sed -e "s#^SECRET_KEY=.*#SECRET_KEY=$(rnd)#" \
      -e "s#^SEED_DEMO=.*#SEED_DEMO=true#" \
      -e "s#^ENVIRONMENT=.*#ENVIRONMENT=production#" \
      -e "s#^CORS_ORIGINS=.*#CORS_ORIGINS=https://$HOST,https://www.$HOST#" \
      -e "s#^PUBLIC_URL=.*#PUBLIC_URL=https://$HOST#" \
      -e "s#^POSTGRES_PASSWORD=.*#POSTGRES_PASSWORD=$PG#" \
      -e "s#^DATABASE_URL=.*#DATABASE_URL=postgresql+asyncpg://bazzy:$PG@postgres:5432/bazzy_video#" \
      -e "s#^B2_ENDPOINT=.*#B2_ENDPOINT=$EP#" \
      -e "s#^B2_BUCKET=.*#B2_BUCKET=bazzyvideo#" \
      -e "s#^B2_KEY_ID=.*#B2_KEY_ID=$KID#" \
      -e "s#^B2_APP_KEY=.*#B2_APP_KEY=$KEY#" \
      -e "s#^CDN_BASE_URL=.*#CDN_BASE_URL=#" \
      -e 's#^\(STRIPE_[A-Z_]*\)=.*_\.\.\.#\1=#' \
      -e 's#^\(OCI_[A-Z_]*\)=your-.*#\1=#' \
      -e 's#^\(CLOUDFLARE_[A-Z_]*\)=your-.*#\1=#' \
      -e "s#^NEXT_PUBLIC_STRIPE_PK=.*#NEXT_PUBLIC_STRIPE_PK=#" \
      .env.example > .env
  set_var .env OAUTH_CLIENTS "[{\"client_id\":\"bazzybox\",\"client_secret\":\"$BOX_SECRET\",\"name\":\"BazzyBox\",\"redirect_uris\":[\"https://box.bazzy.tv/api/auth/bazzy/callback\",\"https://box.bazzy.io/api/auth/bazzy/callback\"],\"trusted\":true,\"wallet\":true},{\"client_id\":\"bazzylive\",\"client_secret\":\"$LIVE_SECRET\",\"name\":\"Bazzy Live\",\"redirect_uris\":[\"https://live.bazzy.tv/auth/bazzy/callback\",\"https://live.bazzy.io/auth/bazzy/callback\"],\"trusted\":true,\"wallet\":true}]"
  chmod 600 .env
  # Same secrets on the BazzyBox / Bazzy Live side → "Sign in with Bazzy TV" works everywhere.
  set_var "$BOX_DIR/.env" BAZZY_AUTH_URL "https://$HOST"
  set_var "$BOX_DIR/.env" BAZZY_CLIENT_SECRET "$BOX_SECRET"
  set_var "$LIVE_DIR/.env" LIVE_BAZZY_AUTH_URL "https://$HOST"
  set_var "$LIVE_DIR/.env" LIVE_BAZZY_CLIENT_SECRET "$LIVE_SECRET"
  echo "wrote .env (and linked BazzyBox + Bazzy Live sign-in)"
fi

say "Build and start Bazzy TV (first time ~10 minutes)"
docker compose up -d --build
for i in $(seq 1 90); do curl -fs -o /dev/null http://127.0.0.1:3000/ && break; sleep 4; done
curl -fs -o /dev/null http://127.0.0.1:3000/ && echo "  Bazzy TV website is up on this Mac" || { echo "  Website didn't answer: docker compose logs --tail 50 frontend api"; exit 1; }

if [ -f "$TUNNEL_YML" ]; then
  say "Tunnel: https://$HOST → this Mac"
  Y="$TUNNEL_YML"
  for h in "$HOST" "www.$HOST"; do
    if ! grep -q "hostname: $h\$" "$Y"; then
      awk -v h="$h" '/- service: http_status:404/ {print "  - hostname: " h; print "    service: http://127.0.0.1:3000"} {print}' "$Y" > "$Y.tmp" && mv "$Y.tmp" "$Y"
    fi
    "$LIVE_DIR/bin/cloudflared" tunnel route dns --overwrite-dns "$(awk '/^tunnel:/{print $2}' "$Y")" "$h" \
      || echo "  could not route $h — is $HOST added to your Cloudflare account?"
  done
  launchctl kickstart -k "gui/$(id -u)/io.bazzy.stack" && echo "  restarted tunnel, BazzyBox and Bazzy Live"
fi

cat <<EOF

Done. Bazzy TV: https://$HOST (give DNS a few minutes the first time).
• Logs: cd $(pwd) && docker compose logs -f api frontend
• Docker Desktop → Settings → General → "Start Docker Desktop when you sign in" keeps it running after a reboot.
• Payments: add STRIPE_* keys to .env, then rerun this script.
EOF
