"""Extraction accuracy set (spec section 8). Real model, run manually: OPENAI_API_KEY=... pytest -m llm tests/test_extraction_llm.py -s"""
import os

import pytest

from homefinder.integrations.llm import make_llm
from homefinder.models import Listing
from homefinder.worker.enrich.extract import extract_missing
from tests.test_extraction_cases import load_cases

pytestmark = [pytest.mark.llm, pytest.mark.skipif(not os.environ.get("OPENAI_API_KEY"), reason="needs OPENAI_API_KEY")]


def _match(expected, got) -> bool:
    if isinstance(expected, float) or isinstance(got, float):
        return got is not None and abs(float(expected) - float(got)) <= 0.5
    return expected == got


def test_extraction_precision_and_recall():
    llm = make_llm()
    assert llm is not None
    hit = extracted_total = expected_total = 0
    rows = []
    for i, c in enumerate(load_cases()):
        out = extract_missing(llm, Listing(description=c["text"]))
        exp = c["expected"]
        # precision is measured on the fields the case labels (the label lists only what the text states explicitly)
        scored = {k: v for k, v in out.items() if k in exp}
        ok = sum(_match(exp[k], v) for k, v in scored.items())
        hit += ok
        extracted_total += len(scored)
        expected_total += len(exp)
        rows.append((i, c["source"], len(exp), len(scored), ok))
    precision = hit / extracted_total if extracted_total else 0.0
    recall = hit / expected_total if expected_total else 0.0
    print("\ncase source expected extracted correct")
    for r in rows:
        print(*r)
    print(f"precision={precision:.3f} recall={recall:.3f}")
    assert precision >= 0.9
