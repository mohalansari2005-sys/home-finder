import json

from homefinder.models import Listing
from homefinder.sanity import AGE, BUILT, LAND, PRICE, ROOMS, STREET, clean_float, clean_int

FACINGS = ["north", "south", "east", "west", "northeast", "northwest", "southeast", "southwest"]
EXTRACTABLE: dict[str, dict] = {
    "price": {"type": ["integer", "null"]},
    "bedrooms": {"type": ["integer", "null"]},
    "bathrooms": {"type": ["integer", "null"]},
    "built_area_m2": {"type": ["number", "null"]},
    "land_area_m2": {"type": ["number", "null"]},
    "building_age_years": {"type": ["integer", "null"]},
    "street_width_m": {"type": ["number", "null"]},
    "facing": {"type": ["string", "null"], "enum": FACINGS + [None]},
    "street_count": {"type": ["integer", "null"]},
    "deed_type": {"type": ["string", "null"], "enum": ["electronic", "paper", None]},
    "has_maid_room": {"type": ["boolean", "null"]},
    "has_driver_room": {"type": ["boolean", "null"]},
    "has_yard": {"type": ["boolean", "null"]},
    "has_elevator": {"type": ["boolean", "null"]},
    "district": {"type": ["string", "null"]},
}
_CLEAN = {
    "price": lambda v: clean_int(v, *PRICE), "bedrooms": lambda v: clean_int(v, *ROOMS),
    "bathrooms": lambda v: clean_int(v, *ROOMS), "built_area_m2": lambda v: clean_float(v, *BUILT),
    "land_area_m2": lambda v: clean_float(v, *LAND), "building_age_years": lambda v: clean_int(v, *AGE),
    "street_width_m": lambda v: clean_float(v, *STREET), "street_count": lambda v: clean_int(v, 1, 4),
}
SYSTEM = (
    "أنت تستخرج بيانات عقار من نص إعلان عربي في السعودية. "
    "أعد null لأي قيمة غير مذكورة صراحةً في النص. لا تخمّن ولا تستنتج. "
    "المساحات بالمتر المربع، السعر بالريال، عمر العقار بالسنوات (\"جديد\" = 0). "
    "facing هو اتجاه الواجهة. deed_type: electronic للصك الإلكتروني، paper للصك الورقي."
)


def build_schema(fields: list[str]) -> dict:
    return {"type": "object", "properties": {f: EXTRACTABLE[f] for f in fields},
            "required": fields, "additionalProperties": False}


def extract_missing(llm, listing: Listing) -> dict:
    text = "\n".join(x for x in (listing.title, listing.description) if x)
    missing = [f for f in EXTRACTABLE if getattr(listing, f) is None]
    if not text.strip() or not missing:
        return {}
    raw = llm.extract_json(system=SYSTEM, user=text[:6000], schema=build_schema(missing), name="listing_fields")
    out = {}
    for f in missing:
        v = raw.get(f)
        if v is None:
            continue
        v = _CLEAN[f](v) if f in _CLEAN else v
        if v is not None:
            out[f] = v
    return out
