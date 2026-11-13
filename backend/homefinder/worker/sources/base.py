import random
import time
from collections.abc import Callable, Iterator
from typing import Protocol

from homefinder.schemas import HealthReport, RawListing, SearchQuery


class SourceAdapter(Protocol):
    name: str
    def search(self, q: SearchQuery) -> Iterator[RawListing]: ...
    def fetch(self, source_id: str) -> RawListing | None: ...
    def health(self, sample: list[RawListing]) -> HealthReport: ...


class Pacer:
    """Polite delay between requests: uniform(2,3)s, or uniform(5,10)s with 1% probability. First call is free."""

    def __init__(self, sleep: Callable[[float], None] = time.sleep, rng: random.Random | None = None):
        self._sleep = sleep
        self._rng = rng or random.Random()
        self._first = True

    def wait(self) -> None:
        if self._first:
            self._first = False
            return
        self._sleep(self._rng.uniform(5, 10) if self._rng.random() < 0.01 else self._rng.uniform(2, 3))


def default_health(sample: list[RawListing], min_sample: int = 10, threshold: float = 0.5) -> HealthReport:
    n = len(sample)
    if n == 0:
        return HealthReport(ok=True, sample_size=0, missing_ratio={})
    ratio = {
        "price": sum(r.fields.price is None for r in sample) / n,
        "location": sum(r.fields.lat is None and r.fields.district is None for r in sample) / n,
        "area": sum(r.fields.built_area_m2 is None and r.fields.land_area_m2 is None for r in sample) / n,
    }
    bad = [k for k, v in ratio.items() if v > threshold]
    if n >= min_sample and bad:
        return HealthReport(ok=False, sample_size=n, missing_ratio=ratio,
                            reason=f"missing {', '.join(bad)} in >{int(threshold * 100)}% of {n} results")
    return HealthReport(ok=True, sample_size=n, missing_ratio=ratio)
