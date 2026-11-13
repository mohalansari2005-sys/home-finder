import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location("scrub_fixture", Path(__file__).parents[2] / "scripts" / "scrub_fixture.py")
scrub_mod = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(scrub_mod)


def test_scrub_replaces_personal_data():
    obj = {"user": {"phone": "0551234567", "name": "أبو محمد", "img": "x.jpg"}, "user_id": 991,
           "content": "للتواصل 0551234567 او +966551234567", "deed_number": "4101234567",
           "nested": [{"mobile": "966501112222"}], "price": 1200000}
    out = scrub_mod.scrub(obj)
    assert out["user"] == {"phone": "0500000000", "name": "مالك تجريبي", "img": None}
    assert out["user_id"] == 0
    assert "0551234567" not in out["content"] and "966551234567" not in out["content"]
    assert out["deed_number"] == "0000000000"
    assert out["nested"][0]["mobile"] == "0500000000"
    assert out["price"] == 1200000


def test_scrub_free_text_names_and_numbers():
    txt = "وسيط مباشر\nأبو عبدالعزيز الغامدي\nوسيط عقاري مرخص - رقم فال: 1200047223\nللتواصل مبارك /55111490.5"
    out = scrub_mod.scrub({"content": txt})["content"]
    for leaked in ("الغامدي", "1200047223", "55111490", "مبارك"):
        assert leaked not in out
