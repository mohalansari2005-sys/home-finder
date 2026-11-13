from contextlib import contextmanager

from homefinder.db import session_scope
from homefinder.models import Listing, ListingSource
from homefinder.usage import BudgetExceeded
from homefinder.worker.enrich.extract import EXTRACTABLE, extract_missing
from homefinder.worker.enrich.pipeline import enrich_listing
from homefinder.worker.handlers import WorkerDeps


class FakeLLM:
    def __init__(self, out=None, exc=None): self.out, self.exc, self.calls = out or {}, exc, []
    def extract_json(self, *, system, user, schema, name):
        self.calls.append(schema)
        if self.exc: raise self.exc
        return {k: self.out.get(k) for k in schema["properties"]}


class FakeGoogle:
    def __init__(self): self.calls = 0
    def geocode(self, address): self.calls += 1; return (24.8, 46.6)
    def drive_minutes(self, origin, dests, dep): self.calls += 1; return [15] * len(dests)


def test_extract_only_missing_fields_and_sanity():
    l = Listing(description="فيلا ٥ غرف عمرها ٣٠٠ سنة شارع ٢٠ م", bedrooms=5)
    llm = FakeLLM({"bedrooms": 9, "building_age_years": 300, "street_width_m": 20, "facing": "north"})
    out = extract_missing(llm, l)
    assert "bedrooms" not in llm.calls[0]["properties"]
    assert out == {"street_width_m": 20, "facing": "north"}  # 300-year age rejected by sanity range
    s = llm.calls[0]
    assert s["additionalProperties"] is False and set(s["required"]) == set(s["properties"])


def test_extract_skips_without_text():
    llm = FakeLLM()
    assert extract_missing(llm, Listing(description=None, title=None)) == {} and llm.calls == []


def _deps(llm=None, google=None):
    return WorkerDeps(session_factory=session_scope, adapters={}, llm=llm, google=google, photo_sink=None, http=None)


def test_enrich_without_location(db):
    l = Listing(title="فيلا", description="فيلا للبيع"); db.add(l); db.commit()
    g = FakeGoogle()
    out = enrich_listing(_deps(llm=FakeLLM(), google=g), l.id)
    db.expire_all(); l = db.get(Listing, l.id)
    assert g.calls == 0 and l.geo_precision == "none" and l.commutes == {} and l.enriched_at is not None
    assert out["commutes"] == 0


def test_enrich_geocodes_district_then_commutes(db):
    from tests.worker.test_commute import _place
    _place(db, "work", 24.7, 46.7)
    l = Listing(district="النرجس", city="الرياض"); db.add(l); db.commit()
    g = FakeGoogle()
    enrich_listing(_deps(google=g), l.id)
    db.expire_all(); l = db.get(Listing, l.id)
    assert l.geo_precision == "district" and l.lat == 24.8 and l.commutes == {"work": 15}


def test_enrich_budget_exceeded_keeps_partial_and_requeues(db):
    from homefinder.models import Job
    l = Listing(description="فيلا"); db.add(l); db.commit()
    out = enrich_listing(_deps(llm=FakeLLM(exc=BudgetExceeded("cap"))), l.id)
    assert out["requeued"] is True
    assert db.query(Job).filter(Job.dedupe_key == f"enrich-retry:{l.id}").count() == 1
