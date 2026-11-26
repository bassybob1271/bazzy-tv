#!/bin/bash
# Bazzy Video — start backend in SQLite preview mode
# Run this once in Terminal: bash ~/Desktop/"Bazzy TV"/bazzy-video/start-backend.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$SCRIPT_DIR/backend"

echo "▶ Starting Bazzy backend on http://localhost:8000"
echo "  DB: $BACKEND/bazzy_preview.db"
echo "  Press Ctrl-C to stop"
echo ""

cd "$BACKEND"

# Install deps if needed
if ! /usr/bin/python3 -c "import uvicorn" 2>/dev/null; then
  echo "Installing Python deps..."
  pip3 install --break-system-packages fastapi uvicorn sqlalchemy aiosqlite \
    "pydantic[email]" "python-jose[cryptography]" "passlib[bcrypt]" \
    python-multipart httpx stripe pillow structlog 2>&1 | grep -E "already|Successfully|error" || true
fi

export USE_SQLITE=1
/usr/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
