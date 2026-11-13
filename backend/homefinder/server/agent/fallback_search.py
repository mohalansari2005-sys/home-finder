"""Search from the server when the Mac worker is offline: one page of Aqar via curl_cffi (allowed in the server image)."""
import logging

from homefinder import adapters_state, prefs
from homefinder.schemas import SearchQuery
from homefinder.worker.ingest import ingest_raw
from homefinder.worker.sources.aqar import AqarAdapter
from homefinder.worker.sources.aqar_transport import Blocked, CurlCffiTransport

log = logging.getLogger(__name__)
MAX_INGEST = 20


def run(session_factory, transport_factory=CurlCffiTransport, pacer=None) -> dict:
    with session_factory() as s:
        if adapters_state.is_paused(s, "aqar"):
            return {"paused": True}  # the Mac's scrapes are paused too (blocked / app-version); don't hit Aqar from here
        q = SearchQuery.from_hard_filters(prefs.get_or_create(s).hard_filters).model_copy(update={"max_pages": 1})
    q = q.model_copy(update={"districts": q.districts[:2], "property_types": q.property_types[:1]})
    t = transport_factory()
    try:
        raws = list(AqarAdapter(t, pacer=pacer).search(q))
    except Blocked as e:
        log.warning("fallback search blocked: %s", e)
        return {"blocked": True}
    except Exception as e:  # noqa: BLE001 — network/shape problems must not break the chat turn
        log.warning("fallback search failed: %s", e)
        return {"error": "search_failed"}
    finally:
        t.close()
    n = 0
    for r in raws[:MAX_INGEST]:
        with session_factory() as s:
            ingest_raw(s, r)  # scores the listing and enqueues enrichment for when the Mac comes back
            n += 1
    return {"ingested": n}
