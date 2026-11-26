"""Check the Backblaze B2 connection and set bucket CORS.
Run inside the api container:  docker compose exec api python -m app.b2_check
"""
import sys

from app.core.config import settings
from app.services import storage

if not storage.b2_configured():
    print("✗ B2 not configured — add B2_KEY_ID, B2_APP_KEY and B2_ENDPOINT to .env")
    sys.exit(2)

h = storage.health()
if not h["ok"]:
    print(f"✗ B2 check failed for bucket {settings.B2_BUCKET}: {h.get('error')}")
    sys.exit(1)
print(f"✓ B2 connected — bucket {settings.B2_BUCKET} at {settings.B2_ENDPOINT} (write/read/sign/delete OK)")
print(f"  Video delivery: {h['delivery']}")

origins = sorted(set(settings.ALLOWED_ORIGINS) | {"http://localhost:3000"})
try:
    storage.set_cors(origins)
    print("✓ Bucket CORS set for: " + ", ".join(origins))
except Exception as e:
    print(f"! Couldn't set CORS ({type(e).__name__}: {e}). Use a key with writeBucketSettings, or set it in the B2 web console.")
