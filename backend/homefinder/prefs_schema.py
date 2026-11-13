from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from homefinder.schemas import Facing, PropertyType
from homefinder.scoring import FACTORS

CommuteKind = Literal["school", "work", "university", "airport"]


class HardFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    city: Literal["الرياض"] = "الرياض"
    property_types: list[PropertyType] = Field(default_factory=lambda: ["villa"], min_length=1)
    districts: list[str] = Field(default_factory=list, max_length=30)
    price_max: int | None = Field(None, ge=100_000, le=100_000_000)
    min_bedrooms: int | None = Field(None, ge=1, le=20)
    max_commute: dict[CommuteKind, int] = Field(default_factory=dict)
    building_age_max: int | None = Field(None, ge=0, le=80)
    street_width_min: float | None = Field(None, ge=4, le=100)

    @field_validator("max_commute")
    @classmethod
    def _commute_range(cls, v: dict) -> dict:
        for kind, minutes in v.items():
            if not 5 <= minutes <= 180:
                raise ValueError(f"max_commute {kind} must be 5..180 minutes")
        return v


class Targets(BaseModel):
    model_config = ConfigDict(extra="forbid")
    commute_good_min: int = Field(10, ge=0, le=120)
    commute_bad_min: int = Field(40, ge=5, le=180)
    built_area_ideal: float = Field(350, ge=50, le=5000)
    land_area_ideal: float = Field(400, ge=50, le=20000)
    age_bad_years: int = Field(20, ge=1, le=80)
    street_good_m: float = Field(20, ge=4, le=100)
    street_bad_m: float = Field(10, ge=4, le=100)
    preferred_facings: list[Facing] = Field(default_factory=list)
    bedrooms_ideal: int = Field(5, ge=1, le=20)
    dismissed_suggestions: list[dict] = Field(default_factory=list)  # used by Plan 4


def validate_weights(d: dict) -> dict[str, float]:
    out = {}
    for k, v in d.items():
        if k not in FACTORS:
            raise ValueError(f"unknown factor {k}")
        v = float(v)
        if not 0 <= v <= 3:
            raise ValueError(f"weight {k} out of range")
        out[k] = v
    return out
