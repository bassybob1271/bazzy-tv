"""Bazzy Video — SQLAlchemy ORM Models"""
from sqlalchemy import (
    Column, String, Integer, BigInteger, Float, Boolean,
    DateTime, ForeignKey, Text, Enum, JSON, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base
import enum
import uuid


def gen_uuid():
    return str(uuid.uuid4())


# ── Enums ─────────────────────────────────────────────────────────────────────

class UserRole(str, enum.Enum):
    VIEWER   = "viewer"
    FILMMAKER = "filmmaker"
    ADMIN    = "admin"


class ContentCategory(str, enum.Enum):
    DOCUMENTARY  = "documentary"
    ROMANCE      = "romance"
    CRIME        = "crime"
    HORROR       = "horror"
    NEW_RELEASES = "new_releases"
    COMEDY       = "comedy"


class ContentStatus(str, enum.Enum):
    PENDING    = "pending"
    PROCESSING = "processing"
    REVIEW     = "review"
    LIVE       = "live"
    REJECTED   = "rejected"
    TAKEDOWN   = "takedown"


class TransactionType(str, enum.Enum):
    CREDIT_PURCHASE  = "credit_purchase"
    STREAM_DEBIT     = "stream_debit"
    RENT_DEBIT       = "rent_debit"
    BUY_DEBIT        = "buy_debit"
    FILMMAKER_CREDIT = "filmmaker_credit"
    PAYOUT           = "payout"
    PROMO_GRANT      = "promo_grant"
    REFUND           = "refund"
    APP_DEBIT        = "app_debit"    # BazzyBox storage, Bazzy Live tickets: charged from the shared wallet
    APP_CREDIT       = "app_credit"   # refunds and top-ups made inside those apps


class AccessType(str, enum.Enum):
    SUBSCRIPTION = "subscription"
    RENT         = "rent"
    BUY          = "buy"
    FREE         = "free"


# ── Users ─────────────────────────────────────────────────────────────────────

class OAuthIdentity(Base):
    """A Google or Apple account linked to a Bazzy user (one user can have several)."""
    __tablename__ = "oauth_identities"
    __table_args__ = (Index("ix_oauth_identity_provider_subject", "provider", "subject", unique=True),)

    id         = Column(String(36), primary_key=True, default=gen_uuid)
    user_id    = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider   = Column(String(20), nullable=False)    # google | apple
    subject    = Column(String(255), nullable=False)   # the provider's stable user id ("sub")
    email      = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class OAuthGrant(Base):
    """One-time authorization code issued to an app using "Sign in with Bazzy TV"."""
    __tablename__ = "oauth_grants"

    code_hash      = Column(String(64), primary_key=True)   # sha256 of the code; the code itself is never stored
    client_id      = Column(String(100), nullable=False)
    user_id        = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    redirect_uri   = Column(String(500), nullable=False)
    code_challenge = Column(String(128), nullable=False)
    scope          = Column(String(200), nullable=False, default="openid profile email")
    expires_at     = Column(BigInteger, nullable=False)      # unix seconds
    used           = Column(Boolean, default=False, nullable=False)


class User(Base):
    __tablename__ = "users"

    id              = Column(String(36), primary_key=True, default=gen_uuid)
    email           = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    display_name    = Column(String(100))
    avatar_url      = Column(String(500))
    role            = Column(Enum(UserRole), default=UserRole.VIEWER, nullable=False)
    is_active       = Column(Boolean, default=True)
    is_verified     = Column(Boolean, default=False)
    stripe_customer_id = Column(String(100), unique=True)

    # Credit wallet
    credit_balance    = Column(BigInteger, default=0, nullable=False)
    lifetime_credits  = Column(BigInteger, default=0)

    # Co-op governance
    fan_units         = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    filmmaker_profile = relationship("FilmmakerProfile", back_populates="user", uselist=False, lazy="selectin")
    transactions      = relationship("CreditTransaction", back_populates="user")
    watchlist         = relationship("Watchlist", back_populates="user")
    viewing_history   = relationship("ViewingHistory", back_populates="user")
    access_grants     = relationship("ContentAccess", back_populates="user")

    __table_args__ = (Index("ix_users_email_active", "email", "is_active"),)


class FilmmakerProfile(Base):
    __tablename__ = "filmmaker_profiles"

    id              = Column(String(36), primary_key=True, default=gen_uuid)
    user_id         = Column(String(36), ForeignKey("users.id"), unique=True)
    bio             = Column(Text)
    website         = Column(String(500))
    instagram       = Column(String(100))
    awards          = Column(JSON, default=list)
    verified_badge  = Column(Boolean, default=False)

    # Payout
    stripe_connect_id     = Column(String(100), unique=True)
    stripe_kyc_verified   = Column(Boolean, default=False)
    payout_threshold_usd  = Column(Float, default=25.0)
    total_earned_credits  = Column(BigInteger, default=0)
    total_paid_out_usd    = Column(Float, default=0.0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user     = relationship("User", back_populates="filmmaker_profile")
    titles   = relationship("Title", back_populates="filmmaker")


# ── Content ───────────────────────────────────────────────────────────────────

class Title(Base):
    __tablename__ = "titles"

    id              = Column(String(36), primary_key=True, default=gen_uuid)
    filmmaker_id    = Column(String(36), ForeignKey("filmmaker_profiles.id"), index=True)
    title           = Column(String(300), nullable=False)
    slug            = Column(String(300), unique=True, index=True)
    synopsis        = Column(Text)
    category        = Column(Enum(ContentCategory), nullable=False, index=True)
    tags            = Column(JSON, default=list)
    year            = Column(Integer)
    runtime_minutes = Column(Integer)
    language        = Column(String(10), default="en")
    country         = Column(String(10))
    rating          = Column(String(10))          # G / PG / 17+ / 21+
    festival_laurels= Column(JSON, default=list)

    # Pricing (credits)
    rent_credits     = Column(Integer, default=200)
    buy_credits      = Column(Integer, default=800)
    is_free          = Column(Boolean, default=False)
    is_svod_included = Column(Boolean, default=True)

    # Media
    poster_url       = Column(String(500))
    trailer_url      = Column(String(500))
    cf_stream_uid    = Column(String(100))        # Cloudflare Stream UID
    hls_manifest_url = Column(String(500))

    # DRM / rights
    drm_enabled      = Column(Boolean, default=True)
    geo_restrictions = Column(JSON, default=list)  # ["CN", "RU"] — blocked territories

    # Status
    status           = Column(Enum(ContentStatus), default=ContentStatus.PENDING, index=True)
    published_at     = Column(DateTime(timezone=True))

    # Algo signals (updated by worker)
    view_count       = Column(BigInteger, default=0)
    completion_rate  = Column(Float, default=0.0)   # 0.0 – 1.0
    fan_vote_score   = Column(Float, default=0.0)
    revenue_velocity = Column(Float, default=0.0)   # credits in last 7 days
    editorial_score  = Column(Float, default=0.0)   # manual editor weight

    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), onupdate=func.now())

    filmmaker       = relationship("FilmmakerProfile", back_populates="titles")
    viewing_history = relationship("ViewingHistory", back_populates="title")
    access_grants   = relationship("ContentAccess", back_populates="title")

    __table_args__ = (
        Index("ix_titles_category_status", "category", "status"),
        Index("ix_titles_completion_rate", "completion_rate"),
    )


# ── Credit Ledger ─────────────────────────────────────────────────────────────

class CreditTransaction(Base):
    __tablename__ = "credit_transactions"

    id              = Column(String(36), primary_key=True, default=gen_uuid)
    user_id         = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    title_id        = Column(String(36), ForeignKey("titles.id"), nullable=True)
    transaction_type= Column(Enum(TransactionType), nullable=False, index=True)
    credits_delta   = Column(BigInteger, nullable=False)   # +/- credits
    usd_equivalent  = Column(Float)
    stripe_payment_id = Column(String(100))
    description     = Column(String(500))
    extra_data      = Column("metadata", JSON, default=dict)
    created_at      = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    user = relationship("User", back_populates="transactions")

    __table_args__ = (Index("ix_txn_user_created", "user_id", "created_at"),)


class AppWalletEntry(Base):
    """One wallet across Bazzy TV, Bazzy Live and BazzyBox: every charge or credit an app makes, keyed by
    "<client_id>:<ref>" so a retried request is applied once."""
    __tablename__ = "app_wallet_entries"

    id         = Column(String(200), primary_key=True)
    client_id  = Column(String(64), nullable=False)
    user_id    = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    credits    = Column(BigInteger, nullable=False)
    txn_id     = Column(String(36), ForeignKey("credit_transactions.id"), nullable=True)
    applied    = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class FilmmakerEarning(Base):
    __tablename__ = "filmmaker_earnings"

    id              = Column(String(36), primary_key=True, default=gen_uuid)
    filmmaker_id    = Column(String(36), ForeignKey("filmmaker_profiles.id"), index=True)
    title_id        = Column(String(36), ForeignKey("titles.id"))
    source_txn_id   = Column(String(36), ForeignKey("credit_transactions.id"))
    credits_earned  = Column(BigInteger, nullable=False)
    usd_equivalent  = Column(Float)
    settled         = Column(Boolean, default=False)
    payout_id       = Column(String(36), ForeignKey("payouts.id"), nullable=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())


class Payout(Base):
    __tablename__ = "payouts"

    id                  = Column(String(36), primary_key=True, default=gen_uuid)
    filmmaker_id        = Column(String(36), ForeignKey("filmmaker_profiles.id"), index=True)
    amount_usd          = Column(Float, nullable=False)
    stripe_transfer_id  = Column(String(100), unique=True)
    status              = Column(String(50), default="pending")  # pending/sent/failed
    created_at          = Column(DateTime(timezone=True), server_default=func.now())
    paid_at             = Column(DateTime(timezone=True))


# ── Viewer Activity ───────────────────────────────────────────────────────────

class ContentAccess(Base):
    """Tracks what a user can watch (subscription, rent, buy)"""
    __tablename__ = "content_access"

    id          = Column(String(36), primary_key=True, default=gen_uuid)
    user_id     = Column(String(36), ForeignKey("users.id"), index=True)
    title_id    = Column(String(36), ForeignKey("titles.id"), index=True)
    access_type = Column(Enum(AccessType), nullable=False)
    expires_at  = Column(DateTime(timezone=True))   # None = permanent (buy)
    granted_at  = Column(DateTime(timezone=True), server_default=func.now())

    user  = relationship("User", back_populates="access_grants")
    title = relationship("Title", back_populates="access_grants")


class ViewingHistory(Base):
    __tablename__ = "viewing_history"

    id                = Column(String(36), primary_key=True, default=gen_uuid)
    user_id           = Column(String(36), ForeignKey("users.id"), index=True)
    title_id          = Column(String(36), ForeignKey("titles.id"), index=True)
    session_id        = Column(String(36), index=True)  # for watermark trace
    watch_position_s  = Column(Integer, default=0)       # seconds watched
    completed         = Column(Boolean, default=False)
    credits_debited   = Column(BigInteger, default=0)
    started_at        = Column(DateTime(timezone=True), server_default=func.now())
    last_active_at    = Column(DateTime(timezone=True), onupdate=func.now())

    user  = relationship("User", back_populates="viewing_history")
    title = relationship("Title", back_populates="viewing_history")


class Watchlist(Base):
    __tablename__ = "watchlist"

    id         = Column(String(36), primary_key=True, default=gen_uuid)
    user_id    = Column(String(36), ForeignKey("users.id"), index=True)
    title_id   = Column(String(36), ForeignKey("titles.id"), index=True)
    added_at   = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="watchlist")


class FanVote(Base):
    __tablename__ = "fan_votes"

    id         = Column(String(36), primary_key=True, default=gen_uuid)
    user_id    = Column(String(36), ForeignKey("users.id"), index=True)
    title_id   = Column(String(36), ForeignKey("titles.id"), index=True)
    vote       = Column(Integer, nullable=False)   # 1–5 stars
    created_at = Column(DateTime(timezone=True), server_default=func.now())
