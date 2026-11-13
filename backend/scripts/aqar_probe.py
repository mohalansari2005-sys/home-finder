"""One-off live probe of Aqar. Saves RAW responses to tests/fixtures/aqar/raw/ (gitignored).
Run: .venv/bin/python scripts/aqar_probe.py"""
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from homefinder.worker.sources.aqar_queries import districts_body, find_body  # noqa: E402
from homefinder.worker.sources.aqar_transport import Blocked, CurlCffiTransport, PlaywrightTransport  # noqa: E402

RAW = Path(__file__).parents[1] / "tests" / "fixtures" / "aqar" / "raw"
RAW.mkdir(parents=True, exist_ok=True)
WHERE = {"category": {"eq": 3}, "city_id": {"eq": 21}, "published": {"eq": 1}}


def pace():
    time.sleep(random.uniform(2, 3))


def try_transport(name, t):
    try:
        data = t.post_graphql(find_body(0, WHERE))
        print(name, "OK, listings:", len(data["data"]["Web"]["find"]["listings"]))
        return data
    except Blocked as e:
        print(name, "BLOCKED:", e)
    except Exception as e:  # noqa: BLE001
        print(name, "ERROR:", type(e).__name__, e)
    return None


for name, factory in [("curl_cffi", CurlCffiTransport), ("playwright-headless", lambda: PlaywrightTransport(True)),
                      ("playwright-headed", lambda: PlaywrightTransport(False))]:
    t = factory()
    data = try_transport(name, t)
    if data:
        (RAW / "find_villa_riyadh.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), "utf-8")
        pace(); d = t.post_graphql(districts_body(3, 21))
        (RAW / "districts_villa_riyadh.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), "utf-8")
        first = data["data"]["Web"]["find"]["listings"][0]
        pace(); byid = t.post_graphql(find_body(0, {"id": {"eq": first["id"]}}, size=1))
        (RAW / "find_by_id.json").write_text(json.dumps(byid, ensure_ascii=False, indent=1), "utf-8")
        pace(); priced = t.post_graphql(find_body(0, {**WHERE, "price": {"lte": 1500000}}))
        (RAW / "find_price_lte.json").write_text(json.dumps(priced, ensure_ascii=False, indent=1), "utf-8")
        print("WORKING TRANSPORT:", name)
        t.close()
        break
    t.close()
    pace()
else:
    print("ALL TRANSPORTS BLOCKED")
