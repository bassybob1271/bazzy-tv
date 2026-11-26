"""Bazzy Video — Application Configuration"""
from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List, Optional


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Bazzy Video"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://bazzy:bazzy@localhost:5432/bazzy_video"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_CONNECT_CLIENT_ID: str = ""

    # Video storage: Backblaze B2 (S3-compatible)
    STORAGE_BACKEND: str = "b2"
    B2_ENDPOINT: str = ""          # e.g. https://s3.us-east-005.backblazeb2.com
    B2_REGION: str = ""            # e.g. us-east-005 (read from the endpoint when empty)
    B2_BUCKET: str = "bazzyvideo"  # B2 S3 API needs lowercase
    B2_KEY_ID: str = ""
    B2_APP_KEY: str = ""
    B2_PUBLIC_URL: str = ""        # CDN in front of the bucket, e.g. https://bazzyvideo.b-cdn.net (Bunny)
                                   # empty = players get presigned B2 links (bucket can stay private)
    B2_URL_TTL_SECONDS: int = 6 * 3600      # lifetime of presigned segment links
    STREAM_TOKEN_TTL_SECONDS: int = 6 * 3600
    UPLOAD_DIR: str = "/tmp/bazzy_uploads"  # volume shared by the api and worker containers

    # OCI Storage (legacy, unused)
    OCI_NAMESPACE: str = ""
    OCI_BUCKET_HOT: str = "bazzy-video-hot"
    OCI_BUCKET_COLD: str = "bazzy-video-cold"
    OCI_REGION: str = "us-ashburn-1"

    # Cloudflare
    CF_ACCOUNT_ID: str = ""
    CF_STREAM_TOKEN: str = ""
    CF_ZONE_ID: str = ""

    # Credit Economy — $10 = 1,000 credits
    CREDITS_PER_DOLLAR: int = 100          # 100 cr per $1
    CREDITS_RENT_DEFAULT: int = 200        # 200 cr to rent a title
    CREDITS_BUY_DEFAULT: int = 800         # 800 cr to own a title
    CREDITS_STREAM_PER_MIN: int = 1        # 1 cr per minute watched

    # Payout waterfall
    PLATFORM_PROCESSING_FEE_PCT: float = 0.03   # 3% payment processing
    PLATFORM_DELIVERY_FEE_PCT: float = 0.07     # 7% CDN/delivery
    FILMMAKER_SHARE_PCT: float = 0.80            # 80% of net
    PLATFORM_OPS_PCT: float = 0.10              # 10% platform ops
    RESERVE_POOL_PCT: float = 0.10              # 10% reserve
    MIN_PAYOUT_USD: float = 25.00

    # Public address of the website (the Next.js app, which proxies /api). Used to build
    # OAuth redirect URIs and the post-login redirect, e.g. https://video.bazzy.tv
    PUBLIC_URL: str = "http://localhost:3000"

    # Sign in with Google (Google Cloud console → OAuth client ID, type "Web application").
    # Authorized redirect URI: {PUBLIC_URL}/api/v1/auth/oauth/google/callback
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # Sign in with Apple (developer.apple.com → Identifiers → Services ID; Keys → Sign in with Apple key).
    # Return URL: {PUBLIC_URL}/api/v1/auth/oauth/apple/callback (Apple requires https).
    APPLE_CLIENT_ID: str = ""        # the Services ID, e.g. tv.bazzy.signin
    APPLE_TEAM_ID: str = ""
    APPLE_KEY_ID: str = ""
    APPLE_PRIVATE_KEY: str = ""      # contents of the .p8 file; literal \n sequences are accepted

    # Apps that may "Sign in with Bazzy TV" (OAuth 2.0 authorization code + PKCE), as JSON:
    # [{"client_id":"bazzybox","client_secret":"…","name":"BazzyBox",
    #   "redirect_uris":["https://box.bazzy.io/api/auth/bazzy/callback"],"trusted":true}]
    # trusted = first-party app: skip the consent screen.
    OAUTH_CLIENTS: List[dict] = []
    OAUTH_CODE_TTL_SECONDS: int = 300
    OAUTH_ACCESS_TOKEN_TTL_SECONDS: int = 900

    # CORS
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "https://video.bazzy.tv",
        "https://www.bazzyvideo.com",
    ]

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
