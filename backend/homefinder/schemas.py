from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# townhouse never comes from a source category: only the ad text check (enrich/text_check.py) sets it
PropertyType = Literal["villa", "apartment", "floor", "house", "townhouse"]
Facing = Literal["north", "south", "east", "west", "northeast", "northwest", "southeast", "southwest"]


class CanonicalFields(BaseModel):
    property_type: PropertyType | None = None
    title: str | None = None
    description: str | None = None
    city: str | None = None
    district: str | None = None
    price: int | None = None
    bedrooms: int | None = None
    bathrooms: int | None = None
    livings: int | None = None
    built_area_m2: float | None = None
    land_area_m2: float | None = None
    building_age_years: int | None = None
    street_width_m: float | None = None
    facing: Facing | None = None
    street_count: int | None = None
    deed_type: Literal["electronic", "paper"] | None = None
    has_maid_room: bool | None = None
    has_driver_room: bool | None = None
    has_yard: bool | None = None
    has_elevator: bool | None = None
    lat: float | None = None
    lng: float | None = None


class RawListing(BaseModel):
    source: str
    source_id: str
    url: str
    fields: CanonicalFields
    geo_precision: Literal["exact", "approximate", "district"] | None = None
    photo_urls: list[str] = Field(default_factory=list)
    seller_phone: str | None = None
    seller_name: str | None = None
    listed_at: datetime | None = None
    raw: dict = Field(default_factory=dict)


class SearchQuery(BaseModel):
    city: str = "الرياض"
    property_types: list[PropertyType] = Field(default_factory=lambda: ["villa"])
    districts: list[str] = Field(default_factory=list)
    price_max: int | None = None
    max_pages: int = 5

    @classmethod
    def from_hard_filters(cls, hf: dict) -> "SearchQuery":
        return cls(city=hf.get("city") or "الرياض",
                   property_types=hf.get("property_types") or ["villa"],
                   districts=hf.get("districts") or [],
                   price_max=hf.get("price_max"),
                   max_pages=5 if hf.get("districts") else 10)


class HealthReport(BaseModel):
    ok: bool
    sample_size: int
    missing_ratio: dict[str, float]
    reason: str | None = None
