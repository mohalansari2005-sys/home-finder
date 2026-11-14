from datetime import date, datetime, time
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import (BigInteger, Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text,
                        Time, UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _now():
    return mapped_column(DateTime(timezone=True), server_default=func.now())


class Listing(Base):
    __tablename__ = "listings"
    id: Mapped[int] = mapped_column(primary_key=True)
    property_type: Mapped[str | None] = mapped_column(String(20))  # villa|apartment|floor|house|townhouse
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
    # where the ad text contradicts the source labels, e.g. {"district": {"label": "النرجس", "text": "القيروان"}};
    # None = not checked yet, {} = checked, no conflict
    text_conflicts: Mapped[dict | None] = mapped_column(JSONB)
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
    kind: Mapped[str] = mapped_column(String(12), unique=True)  # home|school|work|university|airport
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
        Index("ix_jobs_type_created", "type", "created_at"),
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
    provider: Mapped[str] = mapped_column(String(16), primary_key=True)  # openai|tomtom
    # Asia/Riyadh. openai: YYYY-MM. tomtom: a YYYY-MM row and a YYYY-MM-DD row (its free tier counts requests).
    period: Mapped[str] = mapped_column(String(10), primary_key=True)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)  # openai only
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


class VisitTrip(Base):
    __tablename__ = "visit_trips"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(160))
    date: Mapped[date] = mapped_column(Date)  # Asia/Riyadh local day
    start_time: Mapped[time] = mapped_column(Time)  # Asia/Riyadh local
    origin_kind: Mapped[str] = mapped_column(String(12))  # home|school|work|university
    origin_lat: Mapped[float] = mapped_column(Float)
    origin_lng: Mapped[float] = mapped_column(Float)
    minutes_per_visit: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(10), default="planned", server_default="planned")  # planned|done|cancelled
    warnings: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    total_drive_min: Mapped[int | None] = mapped_column(Integer)
    skipped_no_location: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = _now()
    stops: Mapped[list["VisitStop"]] = relationship(back_populates="trip", cascade="all, delete-orphan",
                                                    order_by="VisitStop.position")


class VisitStop(Base):
    __tablename__ = "visit_stops"
    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("visit_trips.id", ondelete="CASCADE"), index=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    eta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    etd: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    drive_min: Mapped[int | None] = mapped_column(Integer)
    contact_status: Mapped[str] = mapped_column(String(16), default="not_contacted", server_default="not_contacted")
    rating: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    flags: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))  # removed|price_changed|check_failed
    old_price: Mapped[int | None] = mapped_column(BigInteger)  # price before the change that set "price_changed"
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    trip: Mapped[VisitTrip] = relationship(back_populates="stops")


class VisitPhoto(Base):
    """A photo the family took during a visit. Private: never under the public /photos path."""
    __tablename__ = "visit_photos"
    id: Mapped[int] = mapped_column(primary_key=True)
    stop_id: Mapped[int] = mapped_column(ForeignKey("visit_stops.id", ondelete="CASCADE"), index=True)
    path: Mapped[str] = mapped_column(Text)  # relative to visit_photos_dir, e.g. "7/<uuid>.jpg"


class DistrictDriveCache(Base):
    """Drive minutes between two district centroids (a < b, normalized names). minutes None = no route."""
    __tablename__ = "district_drive_cache"
    a: Mapped[str] = mapped_column(String(120), primary_key=True)
    b: Mapped[str] = mapped_column(String(120), primary_key=True)
    minutes: Mapped[int | None] = mapped_column(Integer)
    computed_at: Mapped[datetime] = _now()
