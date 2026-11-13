import argparse
import getpass
import json
import sys

import bcrypt
from geoalchemy2.elements import WKTElement
from sqlalchemy import select

from homefinder import jobs, prefs
from homefinder.config import get_settings
from homefinder.db import session_scope
from homefinder.models import Place
from homefinder.photos_prune import prune_photos
from homefinder.rescore import rescore_all

KKIA = ("مطار الملك خالد الدولي", 24.9576, 46.6988)


def _set_place(kind: str, name: str, lat: float, lng: float) -> None:
    with session_scope() as s:
        row = s.scalar(select(Place).where(Place.kind == kind)) or Place(kind=kind)
        row.name, row.lat, row.lng = name, lat, lng
        row.geom = WKTElement(f"POINT({lng} {lat})", srid=4326)
        s.add(row)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="homefinder")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("hash-password")
    p = sub.add_parser("set-place")
    p.add_argument("--kind", choices=["school", "work", "university", "airport"], required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--lat", type=float, required=True)
    p.add_argument("--lng", type=float, required=True)
    sub.add_parser("seed-airport")
    f = sub.add_parser("set-filters")
    f.add_argument("--json", required=True)
    sub.add_parser("enqueue-scrape")
    pp = sub.add_parser("prune-photos")  # server cron: delete photos of long-gone listings
    pp.add_argument("--days", type=int, default=30)
    sub.add_parser("rescore")  # recompute every listing's filters and score (run once after a scoring change)
    a = ap.parse_args(argv)

    if a.cmd == "hash-password":
        pw = getpass.getpass("Family password: ")
        if len(pw.encode()) > 72:  # bcrypt's hard limit
            print("كلمة المرور أطول من 72 بايت (الحرف العربي بايتان)، اختر كلمة أقصر", file=sys.stderr)
            raise SystemExit(1)
        print(bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode())
    elif a.cmd == "set-place":
        _set_place(a.kind, a.name, a.lat, a.lng)
    elif a.cmd == "seed-airport":
        _set_place("airport", *KKIA)
    elif a.cmd == "set-filters":
        with session_scope() as s:
            pr = prefs.get_or_create(s)
            pr.hard_filters = {**pr.hard_filters, **json.loads(a.json)}
            s.flush()
            rescore_all(s)  # listings scraped before the change must not keep their old filter result
    elif a.cmd == "prune-photos":
        with session_scope() as s:
            print(f"pruned photos of {prune_photos(s, get_settings().photos_dir, a.days)} listings")
    elif a.cmd == "rescore":
        with session_scope() as s:
            print(f"rescored {rescore_all(s)} listings")
    elif a.cmd == "enqueue-scrape":
        with session_scope() as s:
            print(jobs.enqueue(s, "scrape_search", {"source": "aqar", "from_prefs": True, "scheduled": False},
                               dedupe_key="scrape:aqar", priority=5))


if __name__ == "__main__":
    main()
