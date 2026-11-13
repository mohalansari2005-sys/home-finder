import logging
import time
from collections.abc import Callable
from io import BytesIO
from typing import Protocol

import httpx

log = logging.getLogger(__name__)
MAX_PHOTOS = 10
MAX_SIDE = 1600
PHOTO_DELAY_S = 0.5  # be polite to the listing sites' image hosts


class PhotoSink(Protocol):
    def upload(self, listing_id: int, position: int, data: bytes, phash: str, source_url: str) -> None: ...


def process_image(data: bytes) -> tuple[bytes, str]:
    import imagehash
    from PIL import Image, ImageOps
    im = ImageOps.exif_transpose(Image.open(BytesIO(data))).convert("RGB")
    im.thumbnail((MAX_SIDE, MAX_SIDE))
    out = BytesIO()
    im.save(out, "WEBP", quality=80)
    return out.getvalue(), str(imagehash.phash(im))


def fetch_photos(http: httpx.Client, sink: PhotoSink, listing_id: int, urls: list[str],
                 sleep: Callable[[float], None] = time.sleep) -> int:
    pos = 0
    for i, url in enumerate(urls[:MAX_PHOTOS]):
        if i:
            sleep(PHOTO_DELAY_S)
        try:
            r = http.get(url, timeout=30, follow_redirects=True)
            r.raise_for_status()
            data, ph = process_image(r.content)
            sink.upload(listing_id, pos, data, ph, url)
            pos += 1
        except Exception as e:  # noqa: BLE001 — one bad photo must not stop the rest
            log.warning("photo %s failed: %s", url, e)
    return pos
