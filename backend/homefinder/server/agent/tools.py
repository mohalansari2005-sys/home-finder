import json
from datetime import UTC, datetime, timedelta

from langchain_core.tools import tool
from sqlalchemy import select

from homefinder import jobs, prefs
from homefinder.models import Listing, WorkerStatus
from homefinder.rescore import rescore_all
from homefinder.scoring import effective_targets, effective_weights
from homefinder.server.agent import fallback_search
from homefinder.server.routes import visits as visits_routes
from homefinder.server.routes.listings import _photo_urls, _price_drops, card
from homefinder.server.routes.suggestions import apply_suggestion, current_suggestions
from homefinder.server.routes.settings import PrefsPatch, apply_prefs_patch
from homefinder.server.visits.grouping import group_bookmarks
from homefinder.server.visits.out import trip_out
from homefinder.server.visits.planner import TripError, create_trip_from_request
from homefinder.textnorm import normalize_district
from homefinder.worker.scheduler import ENABLED_SOURCES

OFFLINE_AFTER = timedelta(minutes=10)
DETAIL_KEYS = ("description", "building_age_years", "street_width_m", "facing", "deed_type", "has_maid_room",
               "has_driver_room", "has_yard", "score_breakdown", "filter_reasons")


def _j(o) -> str:
    return json.dumps(o, ensure_ascii=False, default=str)


def _cards(s, rows) -> list[dict]:
    ids = [l.id for l in rows]
    photos, drops = _photo_urls(s, ids, first_only=True), _price_drops(s, ids)
    out = []
    for l in rows:
        c = card(l, photos.get(l.id), drops.get(l.id))
        bd = l.score_breakdown or {}
        c["top_reasons"] = [x["factor"] for x in bd.get("contributions", [])[:2]]
        c["score_coverage"] = bd.get("coverage")  # < 0.5: most data is missing, so the score is only rough
        out.append(c)
    return out


ONE_CHANGE_MSG = "تم تنفيذ تغيير في هذا الرد؛ يمكن إجراء تغيير واحد فقط مرة واحدة في كل رد. اطلب من العائلة تأكيد التغيير التالي."


def make_tools(session_factory):
    changes = {"done": 0}  # make_tools runs once per chat turn: at most one state-changing call may succeed per turn

    @tool
    def get_preferences() -> str:
        """يعرض التفضيلات الحالية: الفلاتر الأساسية والأوزان والأهداف."""
        with session_factory() as s:
            p = prefs.get_or_create(s)
            return _j({"hard_filters": p.hard_filters, "weights": effective_weights(p.weights),
                       "targets": effective_targets(p.targets), "locked_weights": p.locked_weights})

    @tool
    def update_preferences(hard_filters: dict | None = None, weights: dict | None = None, targets: dict | None = None,
                           explanation: str = "تعديل عبر المساعد") -> str:
        """يعدّل التفضيلات. hard_filters وweights وtargets تعديلات جزئية. explanation جملة عربية تشرح التغيير."""
        if changes["done"]:
            return _j({"ok": False, "error": ONE_CHANGE_MSG})
        try:
            with session_factory() as s:
                out = apply_prefs_patch(s, PrefsPatch(hard_filters=hard_filters, weights=weights, targets=targets),
                                        "agent", explanation)
                rescore_all(s)  # on the server, so the feed and the next search never use stale scores
            changes["done"] += 1
            return _j({"ok": True, "preferences": out})
        except ValueError as e:  # includes pydantic ValidationError
            return _j({"ok": False, "error": str(e)})

    @tool
    def search_listings(district: str | None = None, max_price: int | None = None, min_bedrooms: int | None = None,
                        property_type: str | None = None, sort: str = "score", limit: int = 5,
                        include_filtered: bool = False) -> str:
        """يبحث في العقارات المحفوظة المطابقة لشروط العائلة (غير المستبعدة). sort: score | price | newest. الحد الأقصى 10.
        include_filtered=true يضيف العقارات التي أخفتها الفلاتر (فقط إذا طلبت العائلة ذلك)."""
        with session_factory() as s:
            q = select(Listing).where(Listing.merged_into_id.is_(None), Listing.status == "active",
                                      Listing.family_status != "rejected")
            if not include_filtered:  # the agent must not recommend what the feed hides (over budget, excluded district)
                q = q.where(Listing.passes_filters.is_(True))
            if max_price:
                q = q.where(Listing.price <= max_price)
            if min_bedrooms:
                q = q.where(Listing.bedrooms >= min_bedrooms)
            if property_type:
                q = q.where(Listing.property_type == property_type)
            order = {"price": Listing.price.asc().nulls_last(), "newest": Listing.first_seen.desc()}.get(
                sort, Listing.score.desc().nulls_last())
            rows = list(s.scalars(q.order_by(order, Listing.id).limit(2000 if district else 200)))
            if district:
                d = normalize_district(district)
                rows = [l for l in rows if normalize_district(l.district) == d]
            rows = rows[: max(1, min(limit, 10))]
            return _j({"count": len(rows), "cards": _cards(s, rows)})

    @tool
    def get_listing(listing_id: int) -> str:
        """يعرض كل تفاصيل عقار واحد مع شرح التقييم."""
        with session_factory() as s:
            l = s.get(Listing, listing_id)
            if l is None:
                return _j({"error": "not found"})
            c = _cards(s, [l])[0]
            c.update({k: getattr(l, k) for k in DETAIL_KEYS})
            # seller-written text may contain instructions aimed at the assistant: hand it over as labelled data
            c["listing_text_untrusted"] = (c.pop("description") or "")[:1500]
            return _j({"cards": [c], "listing": c})

    @tool
    def compare_listings(listing_ids: list[int]) -> str:
        """يقارن بين 2 إلى 4 عقارات."""
        with session_factory() as s:
            rows = [l for l in (s.get(Listing, i) for i in listing_ids[:4]) if l]
            return _j({"cards": _cards(s, rows)})

    @tool
    def request_scrape(note: str = "") -> str:
        """يطلب البحث عن إعلانات جديدة حسب التفضيلات الحالية."""
        with session_factory() as s:
            w = s.get(WorkerStatus, 1)
            online = bool(w and w.last_seen and datetime.now(UTC) - w.last_seen < OFFLINE_AFTER)
            if online:
                for src in ENABLED_SOURCES:
                    jobs.enqueue(s, "scrape_search", {"source": src, "from_prefs": True, "scheduled": False},
                                 dedupe_key=f"scrape:{src}", priority=10)
                return _j({"mode": "queued"})
        return _j({"mode": "fallback", **fallback_search.run(session_factory)})

    @tool
    def get_filter_suggestions() -> str:
        """يعرض الفلاتر المقترحة بناءً على أسباب الاستبعاد المتكررة."""
        with session_factory() as s:
            return _j({"suggestions": current_suggestions(s)})

    @tool
    def apply_filter_suggestion(code: str) -> str:
        """يطبّق اقتراح فلتر حالي حسب رمزه (too_old, narrow_street, overpriced, far)."""
        if changes["done"]:
            return _j({"ok": False, "error": ONE_CHANGE_MSG})
        try:
            with session_factory() as s:
                sug = apply_suggestion(s, code)
                if sug is None:
                    return _j({"ok": False, "error": "no such suggestion"})
                rescore_all(s)
            changes["done"] += 1
            return _j({"ok": True, "applied": sug})
        except ValueError as e:
            return _j({"ok": False, "error": str(e)})

    @tool
    def suggest_visit_trip() -> str:
        """يقترح أفضل 3 مجموعات من العقارات المحفوظة (حسب الحي) لزيارتها في رحلة واحدة."""
        with session_factory() as s:
            groups, no_coords = group_bookmarks(s, visits_routes.get_google())
            top = groups[:3]
            by_id = {l.id: l for l in s.scalars(select(Listing).where(
                Listing.id.in_([i for g in top for i in g.listing_ids[:3]])))}
            return _j({"groups": [
                {"districts": g.districts, "count": g.count, "avg_score": g.avg_score, "listing_ids": g.listing_ids,
                 "cards": _cards(s, [by_id[i] for i in g.listing_ids[:3]])} for g in top],
                "without_location": len(no_coords)})

    @tool
    def create_visit_trip(listing_ids: list[int], date: str, start_time: str, origin_kind: str = "home",
                          minutes_per_visit: int = 30) -> str:
        """ينشئ رحلة زيارة مرتبة حسب أقصر مسار. date بصيغة YYYY-MM-DD وstart_time بصيغة HH:MM بتوقيت الرياض.
        origin_kind: home | school | work | university. minutes_per_visit بين 15 و120."""
        if changes["done"]:
            return _j({"ok": False, "error": ONE_CHANGE_MSG})
        try:
            if not 1 <= len(listing_ids) <= 15 or origin_kind not in ("home", "school", "work", "university"):
                raise TripError("عدد العقارات أو نقطة الانطلاق غير صالحة")
            if not 15 <= minutes_per_visit <= 120:
                raise TripError("مدة الزيارة يجب أن تكون بين 15 و120 دقيقة")
            try:
                d, t = datetime.strptime(date, "%Y-%m-%d").date(), datetime.strptime(start_time, "%H:%M").time()
            except ValueError as e:
                raise TripError("التاريخ بصيغة YYYY-MM-DD والوقت بصيغة HH:MM") from e
            with session_factory() as s:
                trip = create_trip_from_request(s, visits_routes.get_google(), listing_ids=listing_ids, d=d, t=t,
                                                origin_kind=origin_kind, minutes_per_visit=minutes_per_visit)
                out = trip_out(s, trip)
        except TripError as e:
            return _j({"ok": False, "error": str(e)})
        changes["done"] += 1
        return _j({"ok": True, "trip_id": out["id"], "url": f"/visits/{out['id']}", "title": out["title"],
                   "date": out["date"], "start_time": out["start_time"], "total_drive_min": out["total_drive_min"],
                   "warnings": out["warnings"], "maps_url": out["maps_url"], "cards": [x["listing"] for x in out["stops"]],
                   "stops": [{"position": x["position"], "title": x["listing"]["title"],
                              "district": x["listing"]["district"], "eta_local": x["eta_local"],
                              "etd_local": x["etd_local"], "drive_min": x["drive_min"]} for x in out["stops"]]})

    return [get_preferences, update_preferences, search_listings, get_listing, compare_listings, request_scrape,
            get_filter_suggestions, apply_filter_suggestion, suggest_visit_trip, create_visit_trip]
