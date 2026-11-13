"""Scrub personal data from a captured JSON response before committing it to the PUBLIC repo.
Usage: python scripts/scrub_fixture.py raw.json clean.json"""
import json
import re
import sys

FAKE_PHONE = "0500000000"
PHONE_RE = re.compile(r"(?:\+?966|0)5\d{8}")
LONG_NUM_RE = re.compile(r"\d{8,}(?:\.\d+)?")  # phones in odd formats, licence/deed numbers
NAME_BEFORE_LICENCE_RE = re.compile(r"^[^\n]+(?=\n[^\n]*(?:وسيط عقاري|رقم فال|رقم الرخصة))", re.M)
CONTACT_NAME_RE = re.compile(r"(للتواصل|للتفاوض)\s*:?\s*[^\s/\d]+(?=\s*/)")
MAPS_COORD_RE = re.compile(r"(q=|@|ll=)(-?\d{1,3}\.\d{3})\d*,\s*(-?\d{1,3}\.\d{3})\d*")  # truncate to ~110 m
PLOT_LINE_RE = re.compile(r"(رقم المخطط|رقم القطعة|كود التسويق)\s*:[^\n]*")  # plan/plot numbers pinpoint a house
LICENSEE_RE = re.compile(r"^(\s*(?:صاحب الترخيص|الموظف المسؤول عن الإعلان|صاحب الإعلان|اسم المعلن)\s*:).*$", re.M)
BROKER_RE = re.compile(r"(مكتب|مؤسسة|شركة)\s+(?:\S+\s+){1,4}?(للخدمات العقارية|للعقارات|العقارية)")
GEOHASH_KEEP = 6  # 6 chars is ~600 m
PHONE_KEYS = {"phone", "mobile", "whatsapp", "phone_number"}
ZERO_KEYS = {"user_id", "employee_user_id", "mgr_user_id", "rega_id", "authorId"}
NULL_KEYS = {"img", "avatar", "bml_url"}
REDACT_KEYS = {"deed_number": "0000000000", "ad_license_number": "0000000000"}


def scrub(obj, parent_key: str | None = None):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in PHONE_KEYS and v:
                out[k] = FAKE_PHONE
            elif k == "name" and parent_key in ("user", "author", "seller"):
                out[k] = "مالك تجريبي"
            elif k == "authorUsername" and v:
                out[k] = "مالك تجريبي"
            elif k == "geoHash" and isinstance(v, str):
                out[k] = v[:GEOHASH_KEEP]
            elif k in ("re_REGA_Advertiser_registration_number", "re_REGA_Authorization_number") and v:
                out[k] = "0000000000"
            elif k in ZERO_KEYS and v is not None:
                out[k] = 0
            elif k in NULL_KEYS:
                out[k] = None
            elif k in REDACT_KEYS and v:
                out[k] = REDACT_KEYS[k]
            else:
                out[k] = scrub(v, k)
        return out
    if isinstance(obj, list):
        return [scrub(v, parent_key) for v in obj]
    if isinstance(obj, str):
        obj = MAPS_COORD_RE.sub(lambda m: f"{m.group(1)}{m.group(2)},{m.group(3)}", obj)
        obj = PLOT_LINE_RE.sub(lambda m: f"{m.group(1)}: -", obj)
        obj = BROKER_RE.sub(r"\1 مالك تجريبي \2", obj)
        obj = LICENSEE_RE.sub(r"\1 مالك تجريبي", obj)
        obj = PHONE_RE.sub(FAKE_PHONE, obj)
        obj = NAME_BEFORE_LICENCE_RE.sub("مالك تجريبي", obj)
        obj = CONTACT_NAME_RE.sub(r"\1 مالك تجريبي", obj)
        return LONG_NUM_RE.sub(FAKE_PHONE, obj) if re.search(r"\s", obj) else obj  # free text only, keeps image names
    return obj


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    with open(src, encoding="utf-8") as f:
        data = json.load(f)
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(scrub(data), f, ensure_ascii=False, indent=1)
