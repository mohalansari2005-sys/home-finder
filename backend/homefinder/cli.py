import argparse
import getpass
import json

import bcrypt
from geoalchemy2.elements import WKTElement
from sqlalchemy import select

from homefinder import jobs, prefs
from homefinder.db import session_scope
from homefinder.models import Place

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
    a = ap.parse_args(argv)

    if a.cmd == "hash-password":
        pw = getpass.getpass("Family password: ")
        print(bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode())
    elif a.cmd == "set-place":
        _set_place(a.kind, a.name, a.lat, a.lng)
    elif a.cmd == "seed-airport":
        _set_place("airport", *KKIA)
    elif a.cmd == "set-filters":
        with session_scope() as s:
            pr = prefs.get_or_create(s)
            pr.hard_filters = {**pr.hard_filters, **json.loads(a.json)}
    elif a.cmd == "enqueue-scrape":
        with session_scope() as s:
            print(jobs.enqueue(s, "scrape_search", {"source": "aqar", "from_prefs": True, "scheduled": False},
                               dedupe_key="scrape:aqar", priority=5))


if __name__ == "__main__":
    main()
