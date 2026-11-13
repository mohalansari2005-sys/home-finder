from pathlib import Path

import yaml

from homefinder.worker.enrich.extract import EXTRACTABLE

CASES = Path(__file__).parent / "fixtures" / "extraction" / "cases.yaml"


def load_cases() -> list[dict]:
    return yaml.safe_load(CASES.read_text("utf-8"))


def test_extraction_set_has_30_labeled_cases_from_both_sources():
    cases = load_cases()
    assert len(cases) == 30
    assert sum(c["source"] == "aqar" for c in cases) == 15 and sum(c["source"] == "haraj" for c in cases) == 15
    for c in cases:
        assert c["text"].strip() and c["expected"], c
        assert set(c["expected"]) <= set(EXTRACTABLE), c["expected"]


def test_extraction_cases_are_scrubbed():
    import re
    for c in load_cases():
        assert not re.search(r"(?:\+?966|0)5\d{8}", c["text"].replace("0500000000", "")), "real phone number"
