from datetime import datetime
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import (BigInteger, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text,
                        UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _now():
    return mapped_column(DateTime(timezone=True), server_default=func.now())


class Listing(Base):
    __tablename__ = "listings"
    id: Mapped[int] = mapped_column(primary_key=True)
    property_type: Mapped[str | None] = mapped_column(String(20))  # villa|apartment|floor|house
    title: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(String(80))
    district: Mapped[str | None] = mapped_column(String(120))
    price: Mapped[int | None] = mapped_column(BigInteger)  # SAR
    bedrooms: Mapped[int | None] = mapped_column(Integer)
    bathrooms: Mapped[int | None] = mapped_column(Integer)
    livings: Mapped[int | None] = mapped_column(Integer)
    built_area_m2: Mapped[float | None] = mapped_column(Float)
    land_area_m2: Mapped[float | None] = mapped_column(Float)
    building_age_years: Mapped[int | None] = mapped_column(Integer)
    street_width_m: Mapped[float | None] = mapped_column(Float)
    facing: Mapped[str | None] = mapped_column(String(12))  # north|south|east|west|northeast|...
    street_count: Mapped[int | None] = mapped_column(Integer)
    deed_type: Mapped[str | None] = mapped_column(String(12))  # electronic|paper
    has_maid_room: Mapped[bool | None] = mapped_column(Boolean)
    has_driver_room: Mapped[bool | None] = mapped_column(Boolean)
    has_yard: Mapped[bool | None] = mapped_column(Boolean)
    has_elevator: Mapped[bool | None] = mapped_column(Boolean)
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    geom: Mapped[Any] = mapped_column(Geography("POINT", srid=4326), nullable=True)
    geo_precision: Mapped[str] = mapped_column(String(12), default="none", server_default="none")  # exact|approximate|district|none
    commutes: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    status: Mapped[str] = mapped_column(String(10), default="active", server_default="active")  # active|removed
    family_status: Mapped[str] = mapped_column(String(12), default="new", server_default="new")
    passes_filters: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    filter_reasons: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    score: Mapped[float | None] = mapped_column(Float)
    score_breakdown: Mapped[dict | None] = mapped_column(JSONB)
    merged_into_id: Mapped[int | None] = mapped_column(ForeignKey("listings.id"))
    photos_fetched: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    enriched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_seen: Mapped[datetime] = _now()
    last_seen: Mapped[datetime] = _now()


class ListingSource(Base):
    __tablename__ = "listing_sources"
    __table_args__ = (UniqueConstraint("source", "source_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"), index=True)
    source: Mapped[str] = mapped_column(String(20))
    source_id: Mapped[str] = mapped_column(String(64))
    url: Mapped[str] = mapped_column(Text)
    raw: Mapped[dict] = mapped_column(JSONB)
    photo_urls: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    seller_phone: Mapped[str | None] = mapped_column(String(32))
    seller_name: Mapped[str | None] = mapped_column(String(120))
    listed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = _now()


class PriceHistory(Base):
    __tablename__ = "listing_price_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"), index=True)
    price: Mapped[int] = mapped_column(BigInteger)
    observed_at: Mapped[datetime] = _now()


class Photo(Base):
    __tablename__ = "photos"
    __table_args__ = (UniqueConstraint("listing_id", "position"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    path: Mapped[str] = mapped_column(Text)  # relative to photos_dir, e.g. "12/0.webp"
    phash: Mapped[str | None] = mapped_column(String(32))
    source_url: Mapped[str | None] = mapped_column(Text)


class Place(Base):
    __tablename__ = "places"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(12), unique=True)  # school|work|university|airport
    name: Mapped[str] = mapped_column(String(120))
    geom: Mapped[Any] = mapped_column(Geography("POINT", srid=4326))
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    updated_at: Mapped[datetime] = _now()


class CommuteCache(Base):
    __tablename__ = "commute_cache"
    origin_key: Mapped[str] = mapped_column(String(24), primary_key=True)  # "24.812,46.634"
    place_id: Mapped[int] = mapped_column(ForeignKey("places.id", ondelete="CASCADE"), primary_key=True)
    minutes: Mapped[int | None] = mapped_column(Integer)
    computed_at: Mapped[datetime] = _now()


class Preferences(Base):
    __tablename__ = "preferences"
    id: Mapped[int] = mapped_column(primary_key=True)  # always 1
    hard_filters: Mapped[dict] = mapped_column(JSONB, default=dict)
    weights: Mapped[dict] = mapped_column(JSONB, default=dict)
    targets: Mapped[dict] = mapped_column(JSONB, default=dict)
    locked_weights: Mapped[list] = mapped_column(JSONB, default=list)
    learned_through_reaction_id: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    learn_attempted_through_reaction_id: Mapped[int] = mapped_column(Integer, default=0, server_default="0")  # last learn run, even if skipped
    updated_at: Mapped[datetime] = _now()


class Reaction(Base):
    __tablename__ = "reactions"
    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # bookmark|reject|unreject|visit_rating
    reason_code: Mapped[str | None] = mapped_column(String(24))
    note: Mapped[str | None] = mapped_column(Text)
    rating: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = _now()


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("uq_jobs_active_dedupe", "dedupe_key", unique=True,
              postgresql_where=text("status IN ('pending','claimed')")),
        Index("ix_jobs_pending", "status", "run_after"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    type: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(10), default="pending", server_default="pending")
    priority: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    dedupe_key: Mapped[str | None] = mapped_column(String(120))
    run_after: Mapped[datetime] = _now()
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    result: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = _now()


class WorkerStatus(Base):
    __tablename__ = "worker_status"
    id: Mapped[int] = mapped_column(primary_key=True)  # always 1
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    hostname: Mapped[str | None] = mapped_column(String(120))
    version: Mapped[str | None] = mapped_column(String(32))
    current_job_id: Mapped[int | None] = mapped_column(BigInteger)


class AdapterHealth(Base):
    __tablename__ = "adapter_health"
    source: Mapped[str] = mapped_column(String(20), primary_key=True)
    status: Mapped[str] = mapped_column(String(10), default="ok")  # ok|paused
    reason: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = _now()
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ApiUsage(Base):
    __tablename__ = "api_usage"
    provider: Mapped[str] = mapped_column(String(16), primary_key=True)  # openai|google
    month: Mapped[str] = mapped_column(String(7), primary_key=True)  # YYYY-MM (Asia/Riyadh)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    calls: Mapped[int] = mapped_column(Integer, default=0)


class PreferenceChange(Base):
    __tablename__ = "preference_changes"
    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = _now()
    source: Mapped[str] = mapped_column(String(10))  # user|learner|agent
    diff: Mapped[dict] = mapped_column(JSONB)
    explanation: Mapped[str] = mapped_column(Text)


class ChatThread(Base):
    """Metadata for an assistant conversation. The messages live in the LangGraph Postgres checkpointer."""
    __tablename__ = "chat_threads"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # uuid4
    title: Mapped[str] = mapped_column(String(80), default="", server_default="")
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
