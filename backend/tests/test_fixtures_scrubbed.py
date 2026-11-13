import json
import re
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"
PHONE_RE = re.compile(r"(?:\+?966|0)5\d{8}")


def _walk(o, parent=None):
    if isinstance(o, dict):
        for k, v in o.items():
            yield parent, k, v
            yield from _walk(v, k)
    elif isinstance(o, list):
        for v in o:
            yield from _walk(v, parent)


def test_no_real_phone_numbers_or_names_in_fixtures():
    files = [p for p in FIXTURES.rglob("*.json") if "raw" not in p.parts]
    for p in files:
        text = p.read_text("utf-8")
        for m in PHONE_RE.findall(text):
            assert m.endswith("500000000"), f"real phone number in {p}"
        for parent, k, v in _walk(json.loads(text)):
            if k == "name" and parent in ("user", "author", "seller"):
                assert v in (None, "مالك تجريبي"), f"real seller name in {p}"


def test_no_long_digit_runs_in_free_text():
    long_run = re.compile(r"\d{8,}")
    for p in [p for p in FIXTURES.rglob("*.json") if "raw" not in p.parts]:
        for parent, k, v in _walk(json.loads(p.read_text("utf-8"))):
            if k in ("content", "description", "title") and isinstance(v, str):
                for m in long_run.findall(v):
                    assert m == "0500000000", f"digit run {m} in {k} of {p}"


def test_haraj_fixtures_have_no_identity_or_precise_location():
    precise = re.compile(r"\d{1,3}\.\d{4,},\s*\d{1,3}\.\d{4,}")
    for p in (FIXTURES / "haraj").glob("*.json"):
        text = p.read_text("utf-8")
        assert not precise.search(text), f"precise coordinates in {p}"
        for parent, k, v in _walk(json.loads(text)):
            if k == "authorUsername":
                assert v in (None, "مالك تجريبي"), f"author name in {p}"
            if k == "geoHash":
                assert len(v) <= 6, f"precise geohash in {p}"
        assert not re.search(r"(رقم المخطط|رقم القطعة)\s*:\s*[^\s-]", text), f"plot number in {p}"
        assert "الحمود" not in text and "رقم الموظف" not in text
