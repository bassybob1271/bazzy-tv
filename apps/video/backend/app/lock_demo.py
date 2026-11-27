"""Lock the demo staff logins before the site goes public.

The demo seed creates admin and artist accounts with the shared password "bazzydemo". That's fine on
a laptop and dangerous on the internet. This gives each of them a new random password and prints
them, once, so the person running it can keep them somewhere safe. The demo viewer (demo@bazzy.tv)
keeps the shared password so people can still try the site.

    python -m app.lock_demo
"""
import asyncio
import secrets

from sqlalchemy import select

from app.core.security import hash_password, verify_password
from app.db.database import AsyncSessionLocal
from app.models.models import User

STAFF = ["admin@bazzy.tv", "filmmaker@bazzy.tv", "greenhouse-demo@bazzy.tv"]
DEMO_PASSWORD = "bazzydemo"


async def main() -> None:
    async with AsyncSessionLocal() as db:
        changed = []
        for email in STAFF:
            u = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if not u or not verify_password(DEMO_PASSWORD, u.hashed_password):
                continue  # not there, or already locked
            pw = secrets.token_urlsafe(15)
            u.hashed_password = hash_password(pw)
            changed.append((email, pw))
        await db.commit()
    if not changed:
        print("Demo staff logins are already locked.")
    for email, pw in changed:
        print(f"{email}  {pw}")


if __name__ == "__main__":
    asyncio.run(main())
