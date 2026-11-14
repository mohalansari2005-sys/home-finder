from homefinder.db import session_scope
from homefinder.models import Listing
from homefinder.worker.enrich.pipeline import enrich_listing
from homefinder.worker.enrich.text_check import check_text
from homefinder.worker.ingest import ingest_raw
from tests.worker.test_enrich import FakeLLM, _deps
from tests.worker.test_ingest import raw


def test_district_conflict_is_recorded_but_the_label_stays():
    l = Listing(district="النرجس", property_type="villa", description="فيلا في حي القيروان")
    assert check_text(FakeLLM({"district": "القيروان"}), l) == {"district": {"label": "النرجس", "text": "القيروان"}}
    assert l.district == "النرجس"


def test_same_district_spelled_differently_is_not_a_conflict():
    l = Listing(district="النرجس", property_type="villa", description="فيلا بحي النرجس")
    assert check_text(FakeLLM({"district": "حي النرجس", "property_type": "villa"}), l) == {}


def test_townhouse_in_the_text_becomes_the_type():
    l = Listing(district="النرجس", property_type="villa", description="تاون هاوس للبيع")
    out = check_text(FakeLLM({"property_type": "townhouse"}), l)
    assert out == {"property_type": {"label": "villa", "text": "townhouse"}} and l.property_type == "townhouse"


def test_other_type_conflicts_only_warn():
    l = Listing(district="النرجس", property_type="villa", description="شقة")
    assert check_text(FakeLLM({"property_type": "apartment"}), l)["property_type"]["text"] == "apartment"
    assert l.property_type == "villa"


def test_no_text_no_call():
    llm = FakeLLM()
    assert check_text(llm, Listing(district="النرجس")) == {} and llm.calls == []


def test_enrich_checks_once_and_a_townhouse_fails_a_villa_only_filter(db):
    l = Listing(title="تاون هاوس", description="تاون هاوس في القيروان", district="النرجس", property_type="villa",
                price=1_500_000)
    db.add(l); db.commit()
    llm = FakeLLM({"district": "القيروان", "property_type": "townhouse"})
    enrich_listing(_deps(llm=llm), l.id)
    db.expire_all(); l = db.get(Listing, l.id)
    assert l.property_type == "townhouse" and l.text_conflicts["district"]["text"] == "القيروان"
    assert l.passes_filters is False and l.filter_reasons == ["type_excluded"]
    calls = len(llm.calls)
    enrich_listing(_deps(llm=llm), l.id)
    assert sum("property_type" in c["properties"] and "district" in c["properties"] and len(c["properties"]) == 2
               for c in llm.calls[calls:]) == 0  # the text check does not run again


def test_reingest_keeps_a_townhouse_from_the_text(db):
    r = ingest_raw(db, raw()); db.commit()
    db.get(Listing, r.listing_id).property_type = "townhouse"; db.commit()
    ingest_raw(db, raw(price=1_400_000)); db.commit()
    assert db.get(Listing, r.listing_id).property_type == "townhouse"
