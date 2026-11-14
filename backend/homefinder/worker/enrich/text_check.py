from homefinder.models import Listing
from homefinder.textnorm import normalize_district

TYPES = ["villa", "apartment", "floor", "house", "townhouse"]
SCHEMA = {
    "type": "object",
    "properties": {
        "district": {"type": ["string", "null"]},
        "property_type": {"type": ["string", "null"], "enum": TYPES + [None]},
    },
    "required": ["district", "property_type"],
    "additionalProperties": False,
}
SYSTEM = (
    "أنت تقرأ نص إعلان عقار في الرياض. "
    "district: اسم الحي الذي يقع فيه العقار نفسه كما يذكره النص صراحةً، بدون كلمة \"حي\". "
    "تجاهل الأحياء المذكورة كقريبة أو مجاورة (\"قريب من حي\"، \"بجوار\"). null إذا لم يُذكر. "
    "property_type: نوع العقار كما يصفه النص: villa فيلا، apartment شقة، floor دور، house بيت شعبي، "
    "townhouse تاون هاوس. null إذا لم يُذكر صراحةً."
)


def check_text(llm, listing: Listing) -> dict:
    """Compare what the ad text says with the source labels. A townhouse in the text becomes the listing's type
    (so the type filter applies); everything else is only recorded as a conflict for the family to see."""
    text = "\n".join(x for x in (listing.title, listing.description) if x)
    if not text.strip():
        return {}
    said = llm.extract_json(system=SYSTEM, user=text[:6000], schema=SCHEMA, name="listing_text_check")
    out: dict = {}
    d = (said.get("district") or "").strip()
    if d and listing.district and normalize_district(d) != normalize_district(listing.district):
        out["district"] = {"label": listing.district, "text": d}
    t = said.get("property_type")
    if t in TYPES and listing.property_type and t != listing.property_type:
        out["property_type"] = {"label": listing.property_type, "text": t}
        if t == "townhouse":
            listing.property_type = "townhouse"
    return out
