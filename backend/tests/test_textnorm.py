from homefinder.textnorm import normalize_ar, normalize_district, to_western_digits


def test_normalize_ar_letters_and_diacritics():
    assert normalize_ar("  إِسْكان   الأمير ") == "اسكان الامير"
    assert normalize_ar("مدرسة") == "مدرسه"
    assert normalize_ar("مستشفى") == "مستشفي"


def test_normalize_district_strips_prefix():
    assert normalize_district("حي النرجس") == normalize_district("النرجس") == "النرجس"


def test_western_digits():
    assert to_western_digits("١٬٢٠٠٬٠٠٠") == "1,200,000"
