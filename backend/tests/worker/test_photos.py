from io import BytesIO

import httpx
from PIL import Image

from homefinder.worker.enrich.photos import fetch_photos, process_image


def jpeg(w=3000, h=2000):
    b = BytesIO(); Image.new("RGB", (w, h), (200, 30, 30)).save(b, "JPEG"); return b.getvalue()


def test_process_image_resizes_to_webp():
    data, ph = process_image(jpeg())
    im = Image.open(BytesIO(data))
    assert im.format == "WEBP" and max(im.size) == 1280 and len(ph) == 16


class Sink:
    def __init__(self): self.got = []
    def upload(self, listing_id, position, data, phash, source_url): self.got.append((listing_id, position, source_url))


def test_fetch_photos_skips_broken_and_caps_at_6():
    def h(req):
        if "bad" in str(req.url):
            return httpx.Response(404)
        return httpx.Response(200, content=jpeg(800, 600), headers={"content-type": "image/jpeg"})
    sink = Sink()
    urls = ["https://i/bad.jpg"] + [f"https://i/{i}.jpg" for i in range(15)]
    n = fetch_photos(httpx.Client(transport=httpx.MockTransport(h)), sink, 9, urls, sleep=lambda s: None)
    assert n == 5 and [g[1] for g in sink.got] == list(range(5))  # 6 urls attempted (the cap), one was broken


def test_fetch_photos_paces_requests_to_the_image_host():
    calls, slept = [], []
    def h(req):
        calls.append(len(slept))
        return httpx.Response(200, content=jpeg(400, 300), headers={"content-type": "image/jpeg"})
    urls = [f"https://i/{i}.jpg" for i in range(3)]
    fetch_photos(httpx.Client(transport=httpx.MockTransport(h)), Sink(), 1, urls, sleep=slept.append)
    assert calls == [0, 1, 2]  # a pause before every request except the first
    assert slept and all(s >= 0.5 for s in slept)
