#!/bin/bash
# Set the password of a Bazzy TV account (the one login for Bazzy TV, Bazzy Live and BazzyBox).
# Optionally make it an admin. Run on the Mac mini:
#   bash <(curl -fsSL https://raw.githubusercontent.com/bassybob1271/bazzy-tv/main/apps/video/deploy/mac-mini/set-password.sh)
# The password is typed hidden and passed to the server on stdin, never on the command line.
export PATH="/usr/local/bin:/opt/homebrew/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH"
cd "$HOME/Bazzy TV/bazzy-tv/apps/video" || { echo "Can't find ~/Bazzy TV/bazzy-tv/apps/video"; exit 1; }

read -r -p "Account email: " EMAIL
read -r -s -p "New password (10+ characters): " PW; echo
read -r -s -p "Same password again: " PW2; echo
[ "$PW" = "$PW2" ] || { echo "✗ The two passwords don't match."; exit 1; }
[ ${#PW} -ge 10 ] || { echo "✗ Use at least 10 characters. A few words work well, like: bayou brass night"; exit 1; }
read -r -p "Make this account an admin? (y/N): " ADMIN

PY='
import asyncio, sys
from sqlalchemy import select, func
from app.core.security import hash_password
from app.db.database import AsyncSessionLocal
from app.models.models import User, UserRole
email, pw, admin = [l.rstrip("\n") for l in sys.stdin.readlines()[:3]]
async def main():
    async with AsyncSessionLocal() as db:
        u = (await db.execute(select(User).where(func.lower(User.email) == email.strip().lower()))).scalar_one_or_none()
        if not u:
            print("✗ No Bazzy TV account with that email. Sign up at https://video.bazzy.tv first, then run this again.")
            return
        u.hashed_password = hash_password(pw)
        u.is_verified = True
        u.is_active = True
        if admin.strip().lower().startswith("y"):
            u.role = UserRole.ADMIN
        await db.commit()
        print(f"✓ Password set for {u.email}" + (" (admin)" if u.role == UserRole.ADMIN else "") + ". Use it on video.bazzy.tv, live.bazzy.tv and box.bazzy.tv.")
asyncio.run(main())
'
printf '%s\n%s\n%s\n' "$EMAIL" "$PW" "$ADMIN" | docker compose -p bazzy-video exec -T api python -c "$PY"
