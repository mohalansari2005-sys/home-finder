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
    """Polite delay between requests: uniform(2,3)s, or uniform(5,10)s with 1% probability.

    Time-based: the gap holds across calls and jobs (the adapter, and so the pacer, lives for the whole worker
    process), and idle time counts towards it. The very first call is free."""

    def __init__(self, sleep: Callable[[float], None] = time.sleep, rng: random.Random | None = None,
                 clock: Callable[[], float] = time.monotonic):
        self._sleep = sleep
        self._rng = rng or random.Random()
        self._clock = clock
        self._next_ok: float | None = None

    def wait(self) -> None:
        now = self._clock()
        if self._next_ok is not None and now < self._next_ok:
            self._sleep(self._next_ok - now)
        gap = self._rng.uniform(5, 10) if self._rng.random() < 0.01 else self._rng.uniform(2, 3)
        self._next_ok = max(now, self._next_ok or now) + gap


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
