import re
from datetime import datetime
from urllib.parse import quote, urlencode

from homefinder.textnorm import to_western_digits

AR_WEEKDAYS = ["الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]  # Python weekday() order


def normalize_sa_mobile(raw: str | None) -> str | None:
    """Saudi mobile in any common format -> '9665XXXXXXXX'. Landlines, wrong lengths and garbage -> None."""
    if not raw:
        return None
    d = re.sub(r"\D", "", to_western_digits(raw))
    if d.startswith("00966"):
        d = d[2:]
    if d.startswith("96605") and len(d) == 13:  # 966 followed by the local trunk 0
        d = "966" + d[4:]
    if d.startswith("9665") and len(d) == 12:
        return d
    if d.startswith("05") and len(d) == 10:
        return "966" + d[1:]
    if d.startswith("5") and len(d) == 9:
        return "966" + d
    return None


def _time_ar(dt: datetime) -> str:
    h = dt.hour % 12 or 12
    return f"{h}:{dt.minute:02d} {'صباحاً' if dt.hour < 12 else 'مساءً'}"


def whatsapp_link(phone: str | None, listing_title: str | None, eta_local: datetime | None) -> str | None:
    """wa.me link with a message holding only the listing title, the day and the time (nothing about the family)."""
    n = normalize_sa_mobile(phone)
    if n is None:
        return None
    msg = f"السلام عليكم، شفت إعلانكم \"{listing_title or 'العقار'}\" وحاب أزوره"
    if eta_local:
        msg += f" يوم {AR_WEEKDAYS[eta_local.weekday()]} الساعة {_time_ar(eta_local)}"
    msg += "، هل يناسبكم؟"
    return f"https://wa.me/{n}?text={quote(msg)}"


def _ll(p) -> str:
    return f"{p[0]},{p[1]}"


def google_maps_route(origin, stops) -> str:
    params = {"api": "1", "origin": _ll(origin), "destination": _ll(stops[-1]), "travelmode": "driving"}
    if len(stops) > 1:
        params["waypoints"] = "|".join(_ll(s) for s in stops[:-1])
    return "https://www.google.com/maps/dir/?" + urlencode(params, safe=",|")
