"""Bazzy Video — Application Configuration"""
from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List


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

    # OCI Storage
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
