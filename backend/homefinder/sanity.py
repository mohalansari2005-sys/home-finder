import logging
import re

from homefinder.textnorm import to_western_digits

log = logging.getLogger(__name__)

PRICE = (100_000, 100_000_000)
BUILT = (50, 5_000)
LAND = (50, 20_000)
AGE = (0, 80)
STREET = (4, 100)
ROOMS = (1, 20)
_NUM = re.compile(r"-?\d+(?:\.\d+)?")


def parse_number(v) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    m = _NUM.search(to_western_digits(str(v)).replace(",", ""))
    return float(m.group()) if m else None


def clean_float(v, lo: float, hi: float) -> float | None:
    n = parse_number(v)
    if n is None:
        return None
    if not lo <= n <= hi:
        log.warning("value %r outside sanity range [%s, %s]", v, lo, hi)
        return None
    return n


def clean_int(v, lo: float, hi: float) -> int | None:
    n = clean_float(v, lo, hi)
    return int(round(n)) if n is not None else None
