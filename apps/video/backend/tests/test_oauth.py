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
        "redirect_uris": ["https://box.test/api/auth/bazzy/callback"], "trusted": True,
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
from app.models.models import OAuthIdentity, User  # noqa: E402

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
