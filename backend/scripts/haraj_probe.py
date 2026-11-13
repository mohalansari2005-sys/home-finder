"""Haraj discovery probe (polite, read-only, no login). Documents how the endpoints were found.

Haraj's web client renders tag pages server-side and then calls the public GraphQL endpoint
`https://graphql.haraj.com.sa/?queryName=posts` (query `FetchAds`) from the browser, with no auth.
This script replays that browser call with curl_cffi (browser impersonation) and writes raw responses to
tests/fixtures/haraj/raw/ (git-ignored). Scrub with scripts/scrub_fixture.py before committing anything.

Usage: python scripts/haraj_probe.py  (about 4 requests, >= 2 s apart)
"""
import json
import time
from pathlib import Path

from homefinder.worker.sources.haraj_transport import CurlCffiHaraj

RAW = Path(__file__).parents[1] / "tests" / "fixtures" / "haraj" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

if __name__ == "__main__":
    t = CurlCffiHaraj()
    page = t.search("فلل للبيع", "الرياض", 0)
    (RAW / "search_villas_riyadh.json").write_text(json.dumps(page, ensure_ascii=False, indent=1), "utf-8")
    items = page["data"]["posts"]["items"]
    print("search items:", len(items), "hasNextPage:", page["data"]["posts"]["pageInfo"])
    time.sleep(2.5)
    post = t.post(str(items[0]["id"]))
    (RAW / "post_detail.json").write_text(json.dumps(post, ensure_ascii=False, indent=1), "utf-8")
    print("post:", post["id"] if post else None)
    t.close()
