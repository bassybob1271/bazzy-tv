"""Bazzy Video as a sign-in provider: "Sign in with Bazzy TV" for apps like BazzyBox.

Standard OAuth 2.0 authorization code flow with PKCE (S256), for confidential clients
registered in settings.OAUTH_CLIENTS:

  1. The app sends the browser to {PUBLIC_URL}/oauth/authorize?response_type=code&client_id=…
     &redirect_uri=…&state=…&code_challenge=…&code_challenge_method=S256 (a website page).
  2. That page signs the user in if needed, shows consent (skipped for trusted first-party apps)
     and calls POST /api/v1/oauth/authorize, which returns the redirect back to the app with ?code.
  3. The app's server exchanges the code: POST /api/v1/oauth/token (client secret + code_verifier).
  4. It reads the user: GET /api/v1/oauth/userinfo with the access token.

Access tokens are JWTs with typ=oauth_access and aud=client_id. The website's session check
rejects them, so a token given to an app can't act as a Bazzy session.
"""
from __future__ import annotations

import base64
import hashlib
import secrets
import time
from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl

from fastapi import APIRouter, Depends, Form, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import get_current_user
from app.db.database import get_db
from app.models.models import OAuthGrant, User
import structlog

log = structlog.get_logger()
router = APIRouter(prefix="/oauth", tags=["oauth"])

SCOPES = {"openid", "profile", "email"}
ACCESS_TYP = "oauth_access"


def _clients() -> dict[str, dict]:
    return {c["client_id"]: c for c in settings.OAUTH_CLIENTS if c.get("client_id")}


def _client(client_id: str, redirect_uri: str) -> dict:
    c = _clients().get(client_id)
    if not c:
        raise HTTPException(400, "unknown app")
    if redirect_uri not in c.get("redirect_uris", []):  # exact match only
        raise HTTPException(400, "redirect_uri is not registered for this app")
    return c


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def _s256(verifier: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()


def _with_params(uri: str, params: dict[str, str]) -> str:
    u = urlparse(uri)
    q = parse_qsl(u.query, keep_blank_values=True) + list(params.items())
    return urlunparse(u._replace(query=urlencode(q)))


def _oauth_error(error: str, description: str, status: int = 400) -> JSONResponse:
    return JSONResponse({"error": error, "error_description": description}, status_code=status, headers={"Cache-Control": "no-store"})


# ── step 2: the website page validates the request, then asks for a code ───────

@router.get("/clients/{client_id}")
async def client_info(client_id: str, redirect_uri: str):
    """Public: lets the consent page show the app's name before the user approves."""
    c = _client(client_id, redirect_uri)
    return {"client_id": client_id, "name": c.get("name", client_id), "trusted": bool(c.get("trusted"))}


class AuthorizeRequest(BaseModel):
    client_id: str
    redirect_uri: str
    state: str = ""
    code_challenge: str
    code_challenge_method: str = "S256"
    scope: str = "openid profile email"


@router.post("/authorize")
async def authorize(req: AuthorizeRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    _client(req.client_id, req.redirect_uri)
    if req.code_challenge_method != "S256" or not (43 <= len(req.code_challenge) <= 128):
        raise HTTPException(400, "PKCE with code_challenge_method=S256 is required")
    scope = " ".join(s for s in req.scope.split() if s in SCOPES) or "openid"
    code = secrets.token_urlsafe(32)
    db.add(OAuthGrant(
        code_hash=_sha256(code), client_id=req.client_id, user_id=user.id, redirect_uri=req.redirect_uri,
        code_challenge=req.code_challenge, scope=scope, expires_at=int(time.time()) + settings.OAUTH_CODE_TTL_SECONDS,
    ))
    await db.commit()
    log.info("oauth.authorize", client_id=req.client_id, user_id=user.id)
    params = {"code": code}
    if req.state:
        params["state"] = req.state
    return {"redirect": _with_params(req.redirect_uri, params)}


# ── step 3: the app's server swaps the code for a token ────────────────────────

def _basic_auth(header: str | None) -> tuple[str, str] | None:
    if not header or not header.lower().startswith("basic "):
        return None
    try:
        raw = base64.b64decode(header[6:]).decode()
        cid, _, secret = raw.partition(":")
        return cid, secret
    except (ValueError, UnicodeDecodeError):
        return None


@router.post("/token")
async def token(
    grant_type: str = Form(...),
    code: str = Form(...),
    redirect_uri: str = Form(...),
    code_verifier: str = Form(...),
    client_id: str | None = Form(None),
    client_secret: str | None = Form(None),
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
):
    if grant_type != "authorization_code":
        return _oauth_error("unsupported_grant_type", "only authorization_code is supported")
    basic = _basic_auth(authorization)
    if basic:
        client_id, client_secret = basic
    c = _clients().get(client_id or "")
    if not c or not client_secret or not secrets.compare_digest(str(c.get("client_secret", "")), client_secret):
        return _oauth_error("invalid_client", "client authentication failed", 401)

    # Mark the code used in the same statement that checks it, so it can only ever be redeemed once.
    now = int(time.time())
    res = await db.execute(
        update(OAuthGrant)
        .where(OAuthGrant.code_hash == _sha256(code), OAuthGrant.used == False, OAuthGrant.expires_at >= now)  # noqa: E712
        .values(used=True)
        .returning(OAuthGrant.client_id, OAuthGrant.user_id, OAuthGrant.redirect_uri, OAuthGrant.code_challenge, OAuthGrant.scope)
    )
    row = res.first()
    await db.commit()
    if not row:
        return _oauth_error("invalid_grant", "the code is invalid, expired or already used")
    g_client, g_user, g_redirect, g_challenge, g_scope = row
    if g_client != client_id or g_redirect != redirect_uri:
        return _oauth_error("invalid_grant", "the code was issued to a different app or redirect_uri")
    if not secrets.compare_digest(_s256(code_verifier), g_challenge):
        return _oauth_error("invalid_grant", "PKCE verification failed")

    user = await db.get(User, g_user)
    if not user or not user.is_active:
        return _oauth_error("invalid_grant", "the account is disabled")

    ttl = settings.OAUTH_ACCESS_TOKEN_TTL_SECONDS
    access = jwt.encode(
        {"sub": user.id, "aud": client_id, "typ": ACCESS_TYP, "scope": g_scope, "iat": now, "exp": now + ttl},
        settings.SECRET_KEY, algorithm=settings.ALGORITHM,
    )
    log.info("oauth.token", client_id=client_id, user_id=user.id)
    return JSONResponse(
        {"access_token": access, "token_type": "Bearer", "expires_in": ttl, "scope": g_scope},
        headers={"Cache-Control": "no-store"},
    )


# ── step 4: who signed in ──────────────────────────────────────────────────────

@router.get("/userinfo")
async def userinfo(authorization: str | None = Header(None), db: AsyncSession = Depends(get_db)):
    if not authorization or not authorization.lower().startswith("bearer "):
        return _oauth_error("invalid_token", "missing bearer token", 401)
    try:
        claims = jwt.decode(authorization[7:], settings.SECRET_KEY, algorithms=[settings.ALGORITHM], options={"verify_aud": False})
    except JWTError:
        return _oauth_error("invalid_token", "invalid or expired token", 401)
    if claims.get("typ") != ACCESS_TYP or claims.get("aud") not in _clients():
        return _oauth_error("invalid_token", "not an app access token", 401)
    user = await db.get(User, claims["sub"])
    if not user or not user.is_active:
        return _oauth_error("invalid_token", "account disabled", 401)
    scope = set(str(claims.get("scope", "")).split())
    info: dict = {"sub": user.id}
    if "email" in scope:
        info.update(email=user.email, email_verified=bool(user.is_verified))
    if "profile" in scope:
        info.update(name=user.display_name, picture=user.avatar_url, role=getattr(user.role, "value", user.role))
    return JSONResponse(info, headers={"Cache-Control": "no-store"})
