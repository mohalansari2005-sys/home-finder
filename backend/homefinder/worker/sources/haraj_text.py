"""Deterministic parsing of Haraj post bodies. Runs before any LLM gap-fill.

Haraj's API `price` is null on almost every real-estate post; the price is only in the body, so without this
the cross-source dedupe (which needs a price on both sides) can never match a Haraj post with its Aqar twin.
A wrong price is worse than none, so the parser only trusts a number that follows a price keyword and returns
None whenever it is unsure."""
import math
import re

from homefinder.textnorm import normalize_ar, to_western_digits

TEXT_PRICE = (100_000, 50_000_000)  # SAR
WINDOW = 45  # characters after the keyword that may hold the amount

_AR = "ء-ي"
_NUM = r"\d[\d,]*(?:\.\d+)*"
_MILLION = rf"(?:مليون|ملايين)(?![{_AR}])"
_THOUSAND = rf"الف(?![{_AR}])"
_TOKEN = re.compile(rf"(?P<num>{_NUM})|(?P<word>(?<![{_AR}])(?:مليونين|مليون|ملايين|الفين|الف)(?![{_AR}]))")
_UNIT = re.compile(rf"\s*(?:(?P<mil>{_MILLION})|(?P<th>{_THOUSAND}))")
_TAIL = re.compile(rf"\s*و\s*(?:(?P<n>{_NUM})\s*{_THOUSAND}|(?P<half>نصف|نص)(?![{_AR}])|(?P<quarter>ربع)(?![{_AR}]))")
_AMBIGUOUS_TAIL = re.compile(rf"\s*و\s*{_NUM}")
_AREA_AFTER = re.compile(r"\s*(?:م2|م²|متر|م(?![ء-ي]))")
_AREA_BEFORE = re.compile(r"(?:عرض|شارع|مساحه|المساحه|ارض|الارض)\s*[:=]?\s*$")
_PHONE = re.compile(r"(?:00)?966\d{8,9}|0?5\d{8}")
_PHONE_PREFIX = re.compile(r"(?:^|\D)0?5\d\s*[-.]?\s*$")
_PER_METRE = re.compile(r"\s*[:\-]?\s*(?:لل|ال)?متر")

# priority order: the licence block's unit price beats a generic price, which beats the softer wordings
_KEYWORDS = [
    re.compile(rf"(?<![{_AR}])سعر الوحده"),
    re.compile(rf"(?<![{_AR}])[بلو]?(?:ال)?سعر(?:ه|ها)?(?![{_AR}])"),
    re.compile(rf"(?<![{_AR}])المطلوب(?![{_AR}])"),
    re.compile(rf"(?<![{_AR}])الحد(?![{_AR}])"),
]


def _normalize(text: str) -> str:
    return normalize_ar(to_western_digits(text.replace("،", ",")))


def _to_number(s: str) -> float | None:
    s = s.rstrip(",.")
    if re.fullmatch(r"\d{1,3}(?:\.\d{3}){2,}", s):  # 1.850.000
        s = s.replace(".", "")
    s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def _million_tail(t: str, pos: int) -> tuple[float, int] | None:
    """What follows 'مليون': nothing, 'و N ألف', 'ونص', 'وربع'. None when it says something we can't read."""
    m = _TAIL.match(t, pos)
    if m:
        if m.group("n"):
            n = _to_number(m.group("n"))
            return (n * 1_000, m.end()) if n is not None else None
        return (500_000 if m.group("half") else 250_000), m.end()
    if _AMBIGUOUS_TAIL.match(t, pos):
        return None
    return 0.0, pos


def _amount(t: str, m: re.Match) -> tuple[float, int] | None:
    """(value, end) for the token, or None when it cannot be a price (ambiguous or malformed)."""
    if m.group("num"):
        n = _to_number(m.group("num"))
        if n is None:
            return None
        u = _UNIT.match(t, m.end())
        if u is None:
            return n, m.end()
        if u.group("th"):
            return n * 1_000, u.end()
        tail = _million_tail(t, u.end())
        return None if tail is None else (n * 1_000_000 + tail[0], tail[1])
    word = m.group("word")
    base = {"مليونين": 2_000_000, "مليون": 1_000_000, "ملايين": None, "الفين": 2_000, "الف": 1_000}[word]
    if base is None:
        return None
    if word in ("مليون", "مليونين"):
        tail = _million_tail(t, m.end())
        return None if tail is None else (base + tail[0], tail[1])
    return base, m.end()


def _looks_like_phone(t: str, m: re.Match) -> bool:
    if m.group("num") is None:
        return False
    digits = m.group("num").replace(",", "")
    if _PHONE.fullmatch(digits):
        return True
    return bool(_PHONE_PREFIX.search(t[max(0, m.start() - 8):m.start()]))


def _first_price_after(t: str, start: int) -> int | None:
    window = t[start:start + WINDOW]
    pos = 0
    while True:
        m = _TOKEN.search(window, pos)
        if m is None:
            return None
        if _looks_like_phone(window, m):
            pos = m.end()
            continue
        got = _amount(window, m)
        if got is None:
            return None  # ambiguous wording right after the keyword: don't guess further along
        value, end = got
        if _AREA_AFTER.match(window, end) or _AREA_BEFORE.search(window[:m.start()]):
            pos = end  # an area or a street width, not the price
            continue
        value = int(round(value))
        return value if TEXT_PRICE[0] <= value <= TEXT_PRICE[1] else None


def parse_price_from_text(*texts: str | None) -> int | None:
    """Price in SAR from the first text that states one after a price keyword (السعر, سعر الوحدة, المطلوب, الحد).

    Texts are tried in order (body first, then title). Returns None for anything outside 100,000..50,000,000,
    for numbers that are phones, areas or street widths, and for ambiguous wording."""
    for raw in texts:
        if not raw:
            continue
        t = _normalize(raw)
        for kw in _KEYWORDS:
            for m in kw.finditer(t):
                if _PER_METRE.match(t, m.end()):
                    continue  # سعر المتر is a unit rate, not the asking price
                price = _first_price_after(t, m.end())
                if price is not None:
                    return price
    return None


# --- area ---
AREA_RANGE = (50, 20_000)  # m2
_AREA_KEY = re.compile(
    rf"(?<![{_AR}])[بلو]?(?:ال)?مساحه(?:\s+(?:ال)?(?P<k>عقار|ارض|بناء|مبني))?(?![{_AR}])[^\d]{{0,15}}?(?P<n>{_NUM})")
_NOT_AREA_AFTER = re.compile(rf"\s*(?:{_THOUSAND}|{_MILLION}|ريال)")
_AREA_FIELD = {"بناء": "built_area_m2", "مبني": "built_area_m2"}  # عقار, ارض and a bare المساحة mean the plot


def parse_areas_from_text(*texts: str | None) -> dict[str, float]:
    """{'land_area_m2'?, 'built_area_m2'?} from 'مساحة العقار', 'المساحة', 'مساحة الأرض' (land) and 'مساحة البناء' (built).

    Haraj's licence block states one area for the plot, so the unqualified wordings are land. Only values from
    50 to 20,000 m2 are kept. Texts are tried in order; the first valid value per field wins."""
    out: dict[str, float] = {}
    for raw in texts:
        if not raw:
            continue
        t = _normalize(raw)
        for m in _AREA_KEY.finditer(t):
            n = _to_number(m.group("n"))
            if n is None or _NOT_AREA_AFTER.match(t, m.end()) or not AREA_RANGE[0] <= n <= AREA_RANGE[1]:
                continue
            out.setdefault(_AREA_FIELD.get(m.group("k"), "land_area_m2"), int(n) if n == int(n) else n)
    return out


# --- location ---

SAUDI = (16, 33, 34, 56)  # lat min/max, lng min/max
PRECISION_LEVELS = ["exact", "approximate", "district", "none"]
MAX_DISAGREEMENT_M = 2_000
_URL = re.compile(r"https?://\S*(?:google\.[a-z.]+/maps|maps\.google\.[a-z.]+|goo\.gl/maps|maps\.app\.goo\.gl)\S*", re.I)
_COORD = r"(-?\d{1,3}\.\d+)"
_COORD_PATTERNS = [
    re.compile(rf"[?&](?:q|ll|query|center|destination)={_COORD}(?:,|%2C){_COORD}", re.I),
    re.compile(rf"@{_COORD},{_COORD}"),
    re.compile(rf"!3d{_COORD}!4d{_COORD}"),
]


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lng2 - lng1) / 2) ** 2
    return 2 * 6_371_000 * math.asin(math.sqrt(a))


def lower_precision(p: str) -> str:
    return PRECISION_LEVELS[min(PRECISION_LEVELS.index(p) + 1, len(PRECISION_LEVELS) - 1)]


def parse_maps_link(body: str | None) -> tuple[float, float] | None:
    """(lat, lng) from the first Google Maps link in the body that carries coordinates inside Saudi Arabia."""
    for url in _URL.findall(body or ""):
        for pat in _COORD_PATTERNS:
            for m in pat.finditer(url):
                lat, lng = float(m.group(1)), float(m.group(2))
                if SAUDI[0] <= lat <= SAUDI[1] and SAUDI[2] <= lng <= SAUDI[3]:
                    return lat, lng
    return None


# --- seller phone -------------------------------------------------------------------------------------------------
# Haraj never exposes the phone through the API, but sellers often type their mobile into the post. The number is
# personal data: it is returned to the caller only (stored in the private DB), never logged.
_PHONE_CAND = re.compile(
    r"(?<![\d,])(?<!\d[.])(?:\+?\s*(?:00)?966[\s.-]*)?0?5(?:[\s.-]*\d){8}(?!\d|[,.]\d)")
# numbers that are not phones: licence (ترخيص / رخصة فال / فال), ad id (رقم الاعلان ...)
_LICENCE = re.compile(
    rf"(?<![{_AR}])(?:ال)?(?:ترخيص|رخصه|رخص|فال)(?![{_AR}])(?:\s+(?:ال)?(?:اعلان|فال|عقاري|عقاريه))*\s*[:=#]?\s*\d[\d-]*")
_AD_ID = re.compile(
    rf"(?<![{_AR}])(?:رقم\s*(?:ال)?(?:اعلان|معرف|كود|عقار)|(?:ال)?اعلان\s*رقم)(?![{_AR}])\s*[:=#]?\s*\d[\d-]*")
_FILLER_BETWEEN_DIGITS = re.compile(
    rf"(?<=\d)\s*(?<![{_AR}])(?:الرقم|رقم|الجوال|جوال|واتساب|واتس|وتس|اتصال|تواصل)(?![{_AR}])\s*(?=\d)")


def _first_mobile(t: str, exclude: set[str]) -> str | None:
    from homefinder.server.visits.links import normalize_sa_mobile

    for m in _PHONE_CAND.finditer(t):
        digits = re.sub(r"\D", "", m.group())
        n = normalize_sa_mobile(digits)
        if n and digits not in exclude and n not in exclude and n[3:] not in exclude and "0" + n[3:] not in exclude:
            return n
    return None


def parse_phone_from_text(*texts: str | None, exclude: set[str] | None = None) -> str | None:
    """First Saudi mobile written in the texts (body first, then title) as 9665XXXXXXXX, else None.
    Skips landlines, licence numbers, ad ids and prices; `exclude` holds digit strings that are known ids."""
    skip = {re.sub(r"\D", "", to_western_digits(x)) for x in (exclude or set())}
    for raw in texts:
        if not raw:
            continue
        t = _AD_ID.sub(" ", _LICENCE.sub(" ", _normalize(raw)))
        found = _first_mobile(t, skip)
        if found is None:  # a number split by words ("05512 واتس 34567"): retry with the words removed
            found = _first_mobile(_FILLER_BETWEEN_DIGITS.sub(" ", t), skip)
        if found:
            return found
    return None
