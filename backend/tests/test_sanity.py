from homefinder.sanity import PRICE, clean_float, clean_int, parse_number


def test_parse_number_variants():
    assert parse_number("1,200,000") == 1200000
    assert parse_number("١٬٢٠٠٬٠٠٠") == 1200000
    assert parse_number(" 350 م2") == 350
    assert parse_number("") is None and parse_number(None) is None and parse_number("abc") is None
    assert parse_number(12.5) == 12.5


def test_clean_ranges():
    assert clean_int(0, *PRICE) is None
    assert clean_int("1,500,000", *PRICE) == 1500000
    assert clean_float(3, 4, 100) is None
    assert clean_int(True, 1, 20) is None  # bools are not numbers
