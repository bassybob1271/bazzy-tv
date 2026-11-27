"""Sign in with Google/Apple, and "Sign in with Bazzy TV" (OAuth provider), end to end.

Google and Apple are faked: id_tokens are signed with a local RSA key and served from a
patched JWKS, and the code exchange is patched. Everything else runs for real.
"""
import base64
import hashlib
import json
import os
import secrets
import tempfile
from urllib.parse import parse_qs, urlparse

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa

# ── environment before the app is imported ─────────────────────────────────────
_tmp = tempfile.mkdtemp()
_apple_key = ec.generate_private_key(ec.SECP256R1())
os.environ.update({
    "DATABASE_URL": f"sqlite+aiosqlite:///{_tmp}/test.db",
    "SECRET_KEY": "test-secret-" + "x" * 40,
    "SEED_DEMO": "false",
    "PUBLIC_URL": "https://video.test",
    "GOOGLE_CLIENT_ID": "google-client.apps.googleusercontent.com",
    "GOOGLE_CLIENT_SECRET": "google-secret",
    "APPLE_CLIENT_ID": "tv.bazzy.signin",
    "APPLE_TEAM_ID": "TEAM123456",
    "APPLE_KEY_ID": "KEY1234567",
    "APPLE_PRIVATE_KEY": _apple_key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode().replace("\n", "\\n"),
    "OAUTH_CLIENTS": json.dumps([{
        "client_id": "bazzybox", "client_secret": "box-secret", "name": "BazzyBox",
        "redirect_uris": ["https://box.test/api/auth/bazzy/callback"], "trusted": True, "wallet": True,
    }, {
        "client_id": "bazzylive", "client_secret": "live-secret", "name": "Bazzy Live",
        "redirect_uris": ["https://live.test/auth/bazzy/callback"], "trusted": True, "wallet": True,
    }, {
        "client_id": "nowallet", "client_secret": "nw-secret", "name": "Other",
        "redirect_uris": ["https://other.test/cb"],
    }]),
})

import httpx  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from jose import jwk, jwt  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.api.routes import social  # noqa: E402
from app.core.security import hash_password, verify_password  # noqa: E402
from app.db.database import AsyncSessionLocal, Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.models import CreditTransaction, OAuthIdentity, User  # noqa: E402

pytestmark = pytest.mark.asyncio(loop_scope="session")

# A fake identity provider: one RSA key, published as a JWKS.
_rsa = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_rsa_pem = _rsa.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
_pub = jwk.construct(_rsa.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode(), "RS256").to_dict()
_pub.update(kid="test-kid", use="sig", alg="RS256")
_pub = {k: (v.decode() if isinstance(v, bytes) else v) for k, v in _pub.items()}
JWKS = {"keys": [_pub]}
ISS = {"google": "https://accounts.google.com", "apple": "https://appleid.apple.com"}
AUD = {"google": "google-client.apps.googleusercontent.com", "apple": "tv.bazzy.signin"}

# What the fake provider will put in the next id_token.
NEXT: dict = {}


def at_hash(access_token: str) -> str:
    d = hashlib.sha256(access_token.encode()).digest()
    return base64.urlsafe_b64encode(d[: len(d) // 2]).rstrip(b"=").decode()


@pytest_asyncio.fixture(scope="session", loop_scope="session", autouse=True)
async def setup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def fake_jwks(provider, refresh=False):
        return JWKS

    async def fake_exchange(provider, code, verifier):
        assert code == "good-code"
        if provider == "google":
            assert verifier and len(verifier) >= 43  # PKCE verifier from the start step
        access = "provider-access-token"
        claims = {"iss": ISS[provider], "aud": AUD[provider], "iat": 1, "exp": 4_000_000_000, "at_hash": at_hash(access), **NEXT}
        return {"id_token": jwt.encode(claims, _rsa_pem, algorithm="RS256", headers={"kid": "test-kid"}), "access_token": access}

    social.fetch_jwks = fake_jwks
    social.exchange_code = fake_exchange
    yield


def client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://video.test")


async def social_login(provider: str, sub: str, email: str, verified=True, name=None, apple_user=None, tamper_nonce=False, next_path="/wallet"):
    async with client() as c:
        r = await c.get(f"/api/v1/auth/oauth/{provider}/start", params={"next": next_path})
        assert r.status_code == 302
        q = parse_qs(urlparse(r.headers["location"]).query)
        NEXT.clear()
        NEXT.update(sub=sub, email=email, email_verified=verified if provider == "google" else ("true" if verified else "false"),
                    nonce="wrong" if tamper_nonce else q["nonce"][0])
        if name:
            NEXT["name"] = name
        if provider == "google":
            r = await c.get(f"/api/v1/auth/oauth/google/callback", params={"code": "good-code", "state": q["state"][0]})
        else:
            form = {"code": "good-code", "state": q["state"][0]}
            if apple_user:
                form["user"] = json.dumps(apple_user)
            r = await c.post("/api/v1/auth/oauth/apple/callback", data=form)
        assert r.status_code == 303
        return r.headers["location"], q


def fragment(location: str) -> dict:
    return {k: v[0] for k, v in parse_qs(urlparse(location).fragment).items()}


# ── Sign in with Google / Apple ────────────────────────────────────────────────

async def test_providers_listed():
    async with client() as c:
        assert (await c.get("/api/v1/auth/providers")).json() == {"google": True, "apple": True}


async def test_google_start_uses_pkce_and_state_cookie():
    async with client() as c:
        r = await c.get("/api/v1/auth/oauth/google/start")
    loc = urlparse(r.headers["location"])
    q = parse_qs(loc.query)
    assert loc.netloc == "accounts.google.com"
    assert q["redirect_uri"] == ["https://video.test/api/v1/auth/oauth/google/callback"]
    assert q["code_challenge_method"] == ["S256"] and q["scope"] == ["openid email profile"]
    cookie = r.headers["set-cookie"]
    assert "bv_oauth=" in cookie and "HttpOnly" in cookie and "Secure" in cookie and "samesite=none" in cookie.lower()


async def test_google_creates_verified_user_then_reuses_it():
    loc, _ = await social_login("google", "g-100", "New.Person@Example.com", name="New Person")
    assert loc.startswith("https://video.test/auth/callback#")
    f = fragment(loc)
    assert f["role"] == "viewer" and f["next"] == "/wallet"
    async with client() as c:  # the token is a normal website session
        assert (await c.get("/api/v1/wallet/", headers={"Authorization": f"Bearer {f['token']}"})).status_code == 200
    loc2, _ = await social_login("google", "g-100", "new.person@example.com")
    assert fragment(loc2)["user_id"] == f["user_id"]
    async with AsyncSessionLocal() as db:
        u = await db.get(User, f["user_id"])
        assert u.email == "new.person@example.com" and u.is_verified and u.display_name == "New Person"


async def test_google_links_existing_unverified_account_and_retires_its_password():
    async with AsyncSessionLocal() as db:
        db.add(User(id="u-pw", email="owner@example.com", hashed_password=hash_password("old password 123"), display_name="Owner", credit_balance=0))
        await db.commit()
    loc, _ = await social_login("google", "g-200", "owner@example.com")
    assert fragment(loc)["user_id"] == "u-pw"
    async with AsyncSessionLocal() as db:
        u = await db.get(User, "u-pw")
        assert u.is_verified and not verify_password("old password 123", u.hashed_password)
        ids = (await db.execute(select(OAuthIdentity).where(OAuthIdentity.user_id == "u-pw"))).scalars().all()
        assert [(i.provider, i.subject) for i in ids] == [("google", "g-200")]


async def test_unverified_provider_email_is_refused():
    loc, _ = await social_login("google", "g-300", "someone@example.com", verified=False)
    assert "/auth/login?error=" in loc and "verify" in loc


async def test_wrong_nonce_is_refused():
    loc, _ = await social_login("google", "g-400", "nonce@example.com", tamper_nonce=True)
    assert "/auth/login?error=" in loc


async def test_state_mismatch_is_refused():
    async with client() as c:
        await c.get("/api/v1/auth/oauth/google/start")
        r = await c.get("/api/v1/auth/oauth/google/callback", params={"code": "good-code", "state": "forged"})
    assert r.status_code == 303 and "/auth/login?error=" in r.headers["location"]


async def test_open_redirect_is_blocked():
    loc, _ = await social_login("google", "g-500", "redir@example.com", next_path="//evil.example/steal")
    assert fragment(loc)["next"] == "/"


async def test_apple_form_post_with_first_time_name():
    loc, q = await social_login("apple", "a-001.abc", "relay123@privaterelay.appleid.com",
                                apple_user={"name": {"firstName": "Ada", "lastName": "Lovelace"}})
    assert q["response_mode"] == ["form_post"]
    f = fragment(loc)
    async with AsyncSessionLocal() as db:
        assert (await db.get(User, f["user_id"])).display_name == "Ada Lovelace"


async def test_apple_client_secret_is_es256_signed_for_apple():
    secret = social.apple_client_secret()
    pub = _apple_key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    claims = jwt.decode(secret, pub, algorithms=["ES256"], audience="https://appleid.apple.com")
    assert claims["iss"] == "TEAM123456" and claims["sub"] == "tv.bazzy.signin"
    assert jwt.get_unverified_header(secret)["kid"] == "KEY1234567"


# ── Sign in with Bazzy TV (provider) ───────────────────────────────────────────

REDIRECT = "https://box.test/api/auth/bazzy/callback"


def pkce():
    v = secrets.token_urlsafe(48)
    return v, base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).rstrip(b"=").decode()


async def bazzy_session(email="viewer@example.com"):
    loc, _ = await social_login("google", "g-" + email, email)
    return fragment(loc)


async def test_client_info_requires_registered_redirect():
    async with client() as c:
        ok = await c.get("/api/v1/oauth/clients/bazzybox", params={"redirect_uri": REDIRECT})
        assert ok.json() == {"client_id": "bazzybox", "name": "BazzyBox", "trusted": True}
        assert (await c.get("/api/v1/oauth/clients/bazzybox", params={"redirect_uri": "https://evil.test/cb"})).status_code == 400


async def test_full_code_flow_and_single_use_code():
    s = await bazzy_session()
    verifier, challenge = pkce()
    async with client() as c:
        assert (await c.post("/api/v1/oauth/authorize", json={"client_id": "bazzybox", "redirect_uri": REDIRECT, "code_challenge": challenge})).status_code == 401
        r = await c.post("/api/v1/oauth/authorize", headers={"Authorization": f"Bearer {s['token']}"},
                         json={"client_id": "bazzybox", "redirect_uri": REDIRECT, "state": "st-1", "code_challenge": challenge})
        back = urlparse(r.json()["redirect"])
        q = parse_qs(back.query)
        assert f"{back.scheme}://{back.netloc}{back.path}" == REDIRECT and q["state"] == ["st-1"]
        code = q["code"][0]
        form = {"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT, "code_verifier": verifier}

        bad_secret = await c.post("/api/v1/oauth/token", data={**form, "client_id": "bazzybox", "client_secret": "nope"})
        assert bad_secret.status_code == 401 and bad_secret.json()["error"] == "invalid_client"

        basic = base64.b64encode(b"bazzybox:box-secret").decode()
        t = await c.post("/api/v1/oauth/token", data=form, headers={"Authorization": f"Basic {basic}"})
        assert t.status_code == 200, t.text
        access = t.json()["access_token"]

        again = await c.post("/api/v1/oauth/token", data={**form, "client_id": "bazzybox", "client_secret": "box-secret"})
        assert again.json()["error"] == "invalid_grant"  # codes are single use

        me = (await c.get("/api/v1/oauth/userinfo", headers={"Authorization": f"Bearer {access}"})).json()
        assert me["sub"] == s["user_id"] and me["email"] == "viewer@example.com" and me["email_verified"] is True

        # An app token is not a website session, and a website session is not an app token.
        assert (await c.get("/api/v1/wallet/", headers={"Authorization": f"Bearer {access}"})).status_code == 401
        assert (await c.get("/api/v1/oauth/userinfo", headers={"Authorization": f"Bearer {s['token']}"})).status_code == 401


async def test_pkce_mismatch_and_wrong_redirect_fail():
    s = await bazzy_session("pkce@example.com")
    _, challenge = pkce()
    async with client() as c:
        r = await c.post("/api/v1/oauth/authorize", headers={"Authorization": f"Bearer {s['token']}"},
                         json={"client_id": "bazzybox", "redirect_uri": REDIRECT, "code_challenge": challenge})
        code = parse_qs(urlparse(r.json()["redirect"]).query)["code"][0]
        t = await c.post("/api/v1/oauth/token", data={"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT,
                                                      "code_verifier": "x" * 50, "client_id": "bazzybox", "client_secret": "box-secret"})
        assert t.json()["error"] == "invalid_grant"
        bad = await c.post("/api/v1/oauth/authorize", headers={"Authorization": f"Bearer {s['token']}"},
                           json={"client_id": "bazzybox", "redirect_uri": "https://box.test/other", "code_challenge": challenge})
        assert bad.status_code == 400


# ── One wallet for every Bazzy app ─────────────────────────────────────────────

BOX_AUTH = "Basic " + base64.b64encode(b"bazzybox:box-secret").decode()


async def member(credits: int, email: str) -> str:
    async with AsyncSessionLocal() as db:
        u = User(email=email, hashed_password=hash_password("x" * 12), credit_balance=credits, is_verified=True)
        db.add(u)
        await db.commit()
        return u.id


async def test_app_reads_and_charges_the_shared_wallet():
    sub = await member(1000, "wallet1@example.com")
    async with client() as c:
        assert (await c.get(f"/api/v1/apps/wallet/{sub}", headers={"authorization": BOX_AUTH})).json() == {"credits": 1000}
        r = await c.post(f"/api/v1/apps/wallet/{sub}/entries", headers={"authorization": BOX_AUTH},
                         json={"credits": -300, "ref": "plan-1", "note": "Flex, 30 days"})
        assert r.status_code == 200 and r.json() == {"applied": True, "accepted": True, "credits": 700}
        # Retried request: applied once.
        again = await c.post(f"/api/v1/apps/wallet/{sub}/entries", headers={"authorization": BOX_AUTH},
                             json={"credits": -300, "ref": "plan-1", "note": "Flex, 30 days"})
        assert again.json()["applied"] is False and again.json()["credits"] == 700
        # Same ref, different amount: refused.
        assert (await c.post(f"/api/v1/apps/wallet/{sub}/entries", headers={"authorization": BOX_AUTH},
                             json={"credits": -5, "ref": "plan-1"})).status_code == 409
        # Shows on the member's Bazzy TV statement.
        async with AsyncSessionLocal() as db:
            txns = (await db.execute(select(CreditTransaction).where(CreditTransaction.user_id == sub))).scalars().all()
        assert [(t.credits_delta, t.description) for t in txns] == [(-300, "BazzyBox · Flex, 30 days")]


async def test_charge_past_balance_is_refused_and_changes_nothing():
    sub = await member(50, "wallet2@example.com")
    async with client() as c:
        r = await c.post(f"/api/v1/apps/wallet/{sub}/entries", headers={"authorization": BOX_AUTH}, json={"credits": -51, "ref": "big"})
        assert r.status_code == 402 and r.json()["detail"]["credits"] == 50
        ok = await c.post(f"/api/v1/apps/wallet/{sub}/entries", headers={"authorization": BOX_AUTH}, json={"credits": 25, "ref": "refund-1"})
        assert ok.json()["credits"] == 75


async def test_wallet_needs_a_wallet_app_with_its_secret():
    sub = await member(10, "wallet3@example.com")
    async with client() as c:
        bad = "Basic " + base64.b64encode(b"bazzybox:wrong").decode()
        assert (await c.get(f"/api/v1/apps/wallet/{sub}", headers={"authorization": bad})).status_code == 401
        other = "Basic " + base64.b64encode(b"nowallet:nw-secret").decode()
        assert (await c.get(f"/api/v1/apps/wallet/{sub}", headers={"authorization": other})).status_code == 403
        assert (await c.get(f"/api/v1/apps/wallet/{sub}")).status_code == 401


# ── Creators spend what they earn ──────────────────────────────────────────────

from app.core.security import create_access_token  # noqa: E402
from app.models.models import FilmmakerEarning, FilmmakerProfile, UserRole  # noqa: E402


def bearer(sub: str) -> dict:
    return {"authorization": f"Bearer {create_access_token({'sub': sub})}"}


async def filmmaker_with_earnings(email: str, *amounts: int) -> tuple[str, str]:
    async with AsyncSessionLocal() as db:
        u = User(email=email, hashed_password=hash_password("x" * 12), role=UserRole.FILMMAKER, credit_balance=0, is_verified=True)
        db.add(u)
        await db.flush()
        fm = FilmmakerProfile(user_id=u.id, total_earned_credits=sum(amounts))
        db.add(fm)
        await db.flush()
        for a in amounts:
            db.add(FilmmakerEarning(filmmaker_id=fm.id, credits_earned=a, usd_equivalent=a / 100))
        await db.commit()
        return u.id, fm.id


async def test_filmmaker_moves_part_then_all_earnings_into_the_wallet():
    sub, fm_id = await filmmaker_with_earnings("maker@example.com", 600, 900)
    async with client() as c:
        dash = (await c.get("/api/v1/filmmaker/dashboard", headers=bearer(sub))).json()
        assert dash["unsettled_credits"] == 1500 and dash["wallet_credits"] == 0
        r = await c.post("/api/v1/filmmaker/earnings-to-wallet", headers=bearer(sub), json={"credits": 1000})
        assert r.status_code == 200 and r.json() == {"moved_credits": 1000, "credit_balance": 1000, "earnings_left": 500}
        # What's left is still payable to the bank, and only that.
        dash = (await c.get("/api/v1/filmmaker/dashboard", headers=bearer(sub))).json()
        assert dash["unsettled_credits"] == 500 and dash["wallet_credits"] == 1000
        assert (await c.post("/api/v1/filmmaker/earnings-to-wallet", headers=bearer(sub), json={"credits": 501})).status_code == 400
        r = await c.post("/api/v1/filmmaker/earnings-to-wallet", headers=bearer(sub), json={})
        assert r.json() == {"moved_credits": 500, "credit_balance": 1500, "earnings_left": 0}
        # Earned credits pay for BazzyBox storage through the shared wallet.
        r = await c.post(f"/api/v1/apps/wallet/{sub}/entries", headers={"authorization": BOX_AUTH},
                         json={"credits": -999, "ref": "maker-flex", "note": "BazzyBox Flex, 30 days"})
        assert r.json()["credits"] == 501


async def test_musician_paid_from_live_can_spend_earnings():
    sub = await member(0, "musician@example.com")
    async with client() as c:
        for _ in range(2):  # retried by the app: counted once
            r = await c.post(f"/api/v1/apps/wallet/{sub}/earnings", headers={"authorization": BOX_AUTH},
                             json={"gross_credits": 2000, "ref": "show-42", "note": "Greenhouse BK, 10 tickets"})
            # Same split as a film: 2,000 − 3% − 7% = 1,800, and 80% of that is 1,440.
            assert r.status_code == 200 and r.json()["creator_credits"] == 1440
        dash = (await c.get("/api/v1/filmmaker/dashboard", headers=bearer(sub))).json()
        assert dash["unsettled_credits"] == 1440 and dash["titles"] == []
        r = await c.post("/api/v1/filmmaker/earnings-to-wallet", headers=bearer(sub), json={})
        assert r.json()["credit_balance"] == 1440
        # Earning on Live doesn't grant uploading films on Bazzy TV.
        async with AsyncSessionLocal() as db:
            assert (await db.get(User, sub)).role == UserRole.VIEWER


async def test_viewers_without_earnings_get_no_creator_tools():
    sub = await member(0, "justwatching@example.com")
    async with client() as c:
        assert (await c.post("/api/v1/filmmaker/earnings-to-wallet", headers=bearer(sub), json={})).status_code == 403


def test_musicians_and_filmmakers_get_the_same_split():
    from app.services.credit_service import creator_share
    # A 200-credit concert ticket and a 200-credit film rental pay the creator the same.
    assert creator_share(200) == 144



# ── Split sheets: pay everyone who worked on the show ──────────────────────────

LIVE_AUTH = "Basic " + base64.b64encode(b"bazzylive:live-secret").decode()


async def earnings_of(sub: str) -> int:
    async with client() as c:
        r = await c.get("/api/v1/filmmaker/dashboard", headers=bearer(sub))
        return r.json()["unsettled_credits"] if r.status_code == 200 else 0


async def test_live_show_pays_every_collaborator_on_the_split():
    band = await member(0, "band@example.com")
    venue = await member(0, "booking@greenhouse.example")
    producer = await member(0, "producer@example.com")
    async with client() as c:
        r = await c.post("/api/v1/splits", headers=bearer(band), json={
            "name": "Greenhouse BK, Fri Dec 5", "app": "live", "source_ref": "show-dec5",
            "shares": [
                {"email": "band@example.com", "role": "band", "percent": 50},
                {"email": "Booking@Greenhouse.example", "name": "Greenhouse BK", "role": "venue", "percent": 20},
                {"email": "producer@example.com", "role": "producer", "percent": 20},
                {"email": "engineer@example.com", "role": "FOH engineer", "percent": 10},
            ]})
        assert r.status_code == 201, r.text
        sheet = r.json()["id"]
        # Ten 200-credit tickets: 2,000 gross → 1,440 creator share, divided by the sheet.
        r = await c.post(f"/api/v1/apps/wallet/{band}/earnings", headers={"authorization": LIVE_AUTH},
                         json={"gross_credits": 2000, "ref": "dec5-batch1", "source_ref": "show-dec5", "note": "10 tickets"})
        assert [(x["role"], x["credits"], x["held"]) for x in r.json()["split"]] == [
            ("band", 720, False), ("venue", 288, False), ("producer", 288, False), ("FOH engineer", 144, True)]
    assert (await earnings_of(band), await earnings_of(venue), await earnings_of(producer)) == (720, 288, 288)

    # The engineer joins later with that email (verified): their held cut is waiting.
    engineer = await member(0, "engineer@example.com")
    async with client() as c:
        mine = (await c.get("/api/v1/splits", headers=bearer(engineer))).json()
        assert [m["name"] for m in mine] == ["Greenhouse BK, Fri Dec 5"] and mine[0]["owner"] is False
        st = (await c.get(f"/api/v1/splits/{sheet}/statement", headers=bearer(engineer))).json()
        assert st["total_credits"] == 1440 and st["sales"] == 1
        assert {p["email"]: p["held_credits"] for p in st["people"]}["engineer@example.com"] == 0
    assert await earnings_of(engineer) == 144


async def test_split_rules():
    band = await member(0, "rules-band@example.com")
    async with client() as c:
        def sheet(*shares, ref="show-rules"):
            return c.post("/api/v1/splits", headers=bearer(band), json={"name": "Rules", "app": "live", "source_ref": ref, "shares": list(shares)})
        assert (await sheet({"email": "a@x.example", "role": "band", "percent": 60}, {"email": "b@x.example", "role": "venue", "percent": 39})).status_code == 400
        assert (await sheet({"email": "a@x.example", "role": "band", "percent": 50}, {"email": "A@x.example", "role": "venue", "percent": 50})).status_code == 400
        assert (await sheet({"email": "a@x.example", "role": "band", "percent": 33.333}, {"email": "b@x.example", "role": "venue", "percent": 66.667})).status_code == 400
        ok = await sheet({"email": "rules-band@example.com", "role": "band", "percent": 33.34},
                         {"email": "b@x.example", "role": "venue", "percent": 33.33}, {"email": "c@x.example", "role": "producer", "percent": 33.33})
        assert ok.status_code == 201
        assert (await sheet({"email": "a@x.example", "role": "band", "percent": 100})).status_code == 409  # one split per show
        # Rounding leftovers go to the first line, so the cuts always add up to the sale.
        r = await c.post(f"/api/v1/apps/wallet/{band}/earnings", headers={"authorization": LIVE_AUTH},
                         json={"gross_credits": 139, "ref": "rules-1", "source_ref": "show-rules"})
        share = r.json()["creator_credits"]
        assert [x["credits"] for x in r.json()["split"]] == [share - 2 * (share * 3333 // 10000), share * 3333 // 10000, share * 3333 // 10000]
        # Only the owner edits; people not on it can't see it; a split that has paid can't be deleted.
        sid = ok.json()["id"]
        venue = await member(0, "b@x.example")
        stranger = await member(0, "stranger@example.com")
        assert (await c.put(f"/api/v1/splits/{sid}", headers=bearer(venue), json={"name": "Mine now"})).status_code == 403
        assert (await c.get(f"/api/v1/splits/{sid}/statement", headers=bearer(stranger))).status_code == 404
        assert (await c.delete(f"/api/v1/splits/{sid}", headers=bearer(band))).status_code == 409
        # Edits apply to later sales.
        r = await c.put(f"/api/v1/splits/{sid}", headers=bearer(band), json={"shares": [
            {"email": "rules-band@example.com", "role": "band", "percent": 90}, {"email": "b@x.example", "role": "venue", "percent": 10}]})
        assert r.status_code == 200 and [x["percent"] for x in r.json()["shares"]] == [90, 10]


async def test_film_split_needs_a_film_you_own():
    band = await member(0, "nofilm@example.com")
    async with client() as c:
        r = await c.post("/api/v1/splits", headers=bearer(band), json={"name": "Not mine", "app": "tv", "source_ref": "some-title",
                                                                       "shares": [{"email": "nofilm@example.com", "role": "director", "percent": 100}]})
        assert r.status_code == 403


async def test_a_show_without_a_split_pays_the_band():
    band = await member(0, "solo@example.com")
    async with client() as c:
        r = await c.post(f"/api/v1/apps/wallet/{band}/earnings", headers={"authorization": LIVE_AUTH},
                         json={"gross_credits": 200, "ref": "solo-1", "source_ref": "show-solo"})
        assert r.json()["split"] is None
    assert await earnings_of(band) == 144


async def test_invite_signup_confirm_and_get_paid():
    from app.services import mailer
    mailer.OUTBOX.clear()
    band = await member(0, "growth-band@example.com")
    async with client() as c:
        sheet = (await c.post("/api/v1/splits", headers=bearer(band), json={
            "name": "Greenhouse BK, Sat Dec 6", "app": "live", "source_ref": "show-dec6",
            "shares": [{"email": "growth-band@example.com", "role": "band", "percent": 75},
                       {"email": "newbie@example.com", "role": "lighting", "percent": 25}]})).json()
        # The non-member is invited with a join link carrying their email.
        invite = [m for m in mailer.OUTBOX if m["To"] == "newbie@example.com"]
        assert len(invite) == 1 and "Claim your cut" in invite[0].get_body(("html",)).get_content()
        assert "register?email=newbie%40example.com" in invite[0].get_body(("plain",)).get_content()
        await c.post(f"/api/v1/apps/wallet/{band}/earnings", headers={"authorization": LIVE_AUTH},
                     json={"gross_credits": 1000, "ref": "dec6-1", "source_ref": "show-dec6"})  # share 720 → 540 / 180
        st = (await c.get(f"/api/v1/splits/{sheet['id']}/statement", headers=bearer(band))).json()
        newbie_line = {p["email"]: p for p in st["people"]}["newbie@example.com"]
        assert newbie_line["held_credits"] == 180 and "register?email=" in newbie_line["join_url"]

        # Signs up with email + password: unconfirmed, so nothing is released yet.
        r = await c.post("/api/v1/auth/register", json={"email": "newbie@example.com", "password": "longpassword1", "display_name": "Newbie"})
        token = r.json()["access_token"]
        assert (await c.get("/api/v1/filmmaker/dashboard", headers={"authorization": f"Bearer {token}"})).status_code == 403
        # Taps the link in the confirmation email: confirmed, and the held cut lands.
        mail = [m for m in mailer.OUTBOX if m["To"] == "newbie@example.com" and "Confirm" in m["Subject"]][-1]
        link = mail.get_body(("plain",)).get_content().split("/auth/verify?token=")[1].split()[0]
        r = await c.post("/api/v1/auth/verify-email", json={"token": link})
        assert r.json() == {"verified": True, "claimed_credits": 180}
        dash = (await c.get("/api/v1/filmmaker/dashboard", headers={"authorization": f"Bearer {token}"})).json()
        assert dash["unsettled_credits"] == 180
        # The link can't be used as a sign-in.
        assert (await c.get("/api/v1/filmmaker/dashboard", headers={"authorization": f"Bearer {link}"})).status_code == 401


# ── Bazzy Live on the shared backend: one account, one wallet, splits ─────────

from datetime import datetime, timedelta, timezone  # noqa: E402
from app.core.config import settings as _settings  # noqa: E402
from app.models.models import ContentAccess, ContentStatus, LiveState, Title  # noqa: E402


async def approve(title_id: str):
    async with AsyncSessionLocal() as db:
        t = await db.get(Title, title_id)
        t.status = ContentStatus.LIVE
        await db.commit()


async def test_a_concert_from_scheduling_to_split_payouts():
    _settings.MEDIAMTX_HOOK_SECRET = "hook-secret"
    band = await member(0, "the-band@example.com")
    await member(0, "greenhouse@example.com")
    fan = await member(500, "fan@example.com")
    late = await member(150, "late@example.com")
    starts = datetime.now(timezone.utc) + timedelta(days=10)
    async with client() as c:
        # A member with no creator profile schedules a show at Greenhouse BK.
        r = await c.post("/api/v1/live/", headers=bearer(band), json={
            "title": "Four Voices", "performer_name": "The Band", "venue": "Greenhouse BK",
            "starts_at": starts.isoformat(), "category": "concerts"})
        assert r.status_code == 201, r.text
        show = r.json()["title_id"]
        ingest = r.json()["ingest"]
        assert ingest["server_url"].startswith("rtmp://") and "?key=" in ingest["stream_key"]
        # Shows can't be dressed up as films.
        assert (await c.post("/api/v1/live/", headers=bearer(band), json={"title": "x", "starts_at": starts.isoformat(), "category": "documentary"})).status_code == 400

        # The band splits it with the venue; the show id is the split's source.
        r = await c.post("/api/v1/splits", headers=bearer(band), json={
            "name": "Four Voices", "app": "live", "source_ref": show,
            "shares": [{"email": "the-band@example.com", "role": "band", "percent": 70},
                       {"email": "greenhouse@example.com", "role": "venue", "percent": 30}]})
        assert r.status_code == 201

        await approve(show)
        # On Bazzy Live, not in the film catalog.
        upcoming = (await c.get("/api/v1/live/home-rails")).json()["upcoming"]
        assert [t["id"] for t in upcoming] == [show] and upcoming[0]["venue"] == "Greenhouse BK"
        assert show not in [t["id"] for t in (await c.get("/api/v1/titles/")).json()]

        # A fan buys a ticket weeks ahead from the one Bazzy wallet: good through 30 days after the show.
        r = await c.post(f"/api/v1/titles/{show}/rent", headers=bearer(fan))
        assert r.status_code == 200, r.text
        async with AsyncSessionLocal() as db:
            assert (await db.get(User, fan)).credit_balance == 300
            grant = (await db.execute(select(ContentAccess).where(ContentAccess.user_id == fan))).scalar_one()
            assert grant.expires_at.replace(tzinfo=timezone.utc) >= starts + timedelta(days=29, hours=23)
            txn = (await db.execute(select(CreditTransaction).where(CreditTransaction.user_id == fan))).scalars().all()
            assert [t.description for t in txn] == ["Ticket: Four Voices"]
        # 200 → 144 creator share → 101 band (70% + rounding) / 43 venue.
        st = (await c.get(f"/api/v1/splits/{(await c.get('/api/v1/splits', headers=bearer(band))).json()[0]['id']}/statement", headers=bearer(band))).json()
        assert {p["role"]: p["credits"] for p in st["people"]} == {"band": 101, "venue": 43}

        # Not on air yet: the playback endpoint says so.
        assert (await c.get(f"/api/v1/live/{show}/playback", headers=bearer(fan))).json()["live_state"] == "scheduled"

        # The ATEM connects: MediaMTX checks the key, then reports the feed is up.
        pid, key = ingest["stream_key"].split("?key=")
        auth = lambda body: c.post("/api/v1/live/ingest/auth?secret=hook-secret", json=body)
        assert (await auth({"action": "publish", "path": f"live/{pid}", "query": "key=wrong"})).status_code == 401
        assert (await auth({"action": "publish", "path": f"live/{pid}", "query": f"key={key}"})).status_code == 200
        assert (await c.post(f"/api/v1/live/ingest/hook?secret=hook-secret&event=ready&path=live/{pid}")).json()["live_state"] == "on_air"

        # Ticket holders get a pass MediaMTX accepts; no ticket, no stream.
        pb = (await c.get(f"/api/v1/live/{show}/playback", headers=bearer(fan))).json()
        assert pb["live_state"] == "on_air" and pb["hls_url"].endswith(f"/live/{pid}/index.m3u8")
        assert (await auth({"action": "read", "path": f"live/{pid}", "query": f"jwt={pb['token']}"})).status_code == 200
        assert (await auth({"action": "read", "path": f"live/{pid}", "query": "jwt=nope"})).status_code == 401
        # A viewer coming through the Live site's /hls proxy looks like loopback: still needs a pass.
        assert (await auth({"action": "read", "path": f"live/{pid}", "ip": "127.0.0.1", "protocol": "hls"})).status_code == 401
        assert (await auth({"action": "read", "path": f"live/{pid}", "ip": "127.0.0.1", "protocol": "hls", "query": f"jwt={pb['token']}"})).status_code == 200
        # The preview encoder (RTMP from loopback) may still read the show.
        assert (await auth({"action": "read", "path": f"live/{pid}", "ip": "127.0.0.1", "protocol": "rtmp"})).status_code == 200
        assert (await c.get(f"/api/v1/live/{show}/playback", headers=bearer(late))).status_code == 402
        # The pass can't be used to sign in.
        assert (await c.get("/api/v1/wallet/", headers={"authorization": f"Bearer {pb['token']}"})).status_code == 401

        # Someone joining mid-show pays 100, from the same wallet.
        r = await c.post(f"/api/v1/live/{show}/join", headers=bearer(late))
        assert r.json()["credits"] == 100
        async with AsyncSessionLocal() as db:
            assert (await db.get(User, late)).credit_balance == 50

        # The band ends it: it moves to previous shows.
        assert (await c.post(f"/api/v1/live/{show}/end", headers=bearer(band))).json()["live_state"] == "ended"
        rails = (await c.get("/api/v1/live/home-rails")).json()
        assert [t["id"] for t in rails["concerts"]] == [show] and rails["upcoming"] == []
        # Becoming an artist on Live doesn't grant film uploads on Bazzy TV.
        async with AsyncSessionLocal() as db:
            assert (await db.get(User, band)).role == UserRole.VIEWER


async def test_someone_elses_show_is_off_limits():
    owner = await member(0, "owner-artist@example.com")
    other = await member(0, "other-artist@example.com")
    async with client() as c:
        show = (await c.post("/api/v1/live/", headers=bearer(owner), json={
            "title": "Mine", "starts_at": datetime.now(timezone.utc).isoformat()})).json()["title_id"]
        await c.post("/api/v1/live/", headers=bearer(other), json={"title": "Theirs", "starts_at": datetime.now(timezone.utc).isoformat()})
        for path in (f"/api/v1/live/{show}/end", f"/api/v1/live/{show}/rotate-key"):
            assert (await c.post(path, headers=bearer(other))).status_code == 404
        assert (await c.get(f"/api/v1/live/{show}/atem-streaming.xml", headers=bearer(other))).status_code == 404
        xml = await c.get(f"/api/v1/live/{show}/atem-streaming.xml", headers=bearer(owner))
        assert xml.status_code == 200 and "<name>Bazzy Live</name>" in xml.text


async def test_google_sign_in_started_on_live_returns_to_live():
    _settings.LIVE_SITE_URL = "https://live.test"
    async with client() as c:
        r = await c.get("/api/v1/auth/oauth/google/start", params={"next": "/shows", "site": "live"})
        q = parse_qs(urlparse(r.headers["location"]).query)
        NEXT.clear()
        NEXT.update(sub="g-live-fan", email="livefan@example.com", email_verified=True, nonce=q["nonce"][0])
        r = await c.get("/api/v1/auth/oauth/google/callback", params={"code": "good-code", "state": q["state"][0]})
    assert r.status_code == 303 and r.headers["location"].startswith("https://live.test/auth/callback#")
    assert fragment(r.headers["location"])["next"] == "/shows"
