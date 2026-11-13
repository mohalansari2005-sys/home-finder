from homefinder.models import DistrictDriveCache, Listing
from homefinder.server.visits.grouping import group_bookmarks


class G:
    def __init__(self, minutes): self.minutes, self.calls = minutes, 0
    def drive_minutes(self, origin, dests, dep):
        self.calls += 1
        return [self.minutes] * len(dests)


def bm(db, district, lat, lng, score=70, status="bookmarked"):
    l = Listing(district=district, lat=lat, lng=lng, score=score, family_status=status); db.add(l); db.flush(); return l


def test_groups_merge_close_districts(db):
    bm(db, "النرجس", 24.84, 46.65); bm(db, "حي النرجس", 24.842, 46.652)
    bm(db, "الياسمين", 24.82, 46.64)          # ~2.5 km from النرجس
    bm(db, "الشفا", 24.55, 46.70)             # far south
    bm(db, "الملقا", 24.80, 46.60, status="seen")  # not bookmarked
    db.commit()
    g = G(minutes=8)
    groups, no_coords = group_bookmarks(db, g)
    assert no_coords == []
    keys = [set(x.districts) for x in groups]
    assert {"النرجس", "الياسمين"} in keys and {"الشفا"} in keys and len(groups) == 2
    assert groups[0].count == 3
    assert g.calls == 1 and db.query(DistrictDriveCache).count() == 1
    group_bookmarks(db, g)
    assert g.calls == 1  # cached


def test_far_drive_not_merged(db):
    bm(db, "النرجس", 24.84, 46.65); bm(db, "الياسمين", 24.82, 46.64); db.commit()
    groups, _ = group_bookmarks(db, G(minutes=15))
    assert len(groups) == 2


def test_grouping_skips_no_coords(db):
    a = bm(db, "النرجس", None, None); bm(db, "النرجس", 24.84, 46.65); db.commit()
    groups, no_coords = group_bookmarks(db, None)
    assert no_coords == [a.id] and groups[0].count == 1


def test_without_maps_merges_only_within_3km(db):
    bm(db, "النرجس", 24.84, 46.65); bm(db, "الياسمين", 24.82, 46.64)  # ~2.5 km
    bm(db, "الملقا", 24.88, 46.62)  # ~5 km from النرجس: too far without drive times
    db.commit()
    groups, _ = group_bookmarks(db, None)
    assert sorted(len(g.districts) for g in groups) == [1, 2]
    assert db.query(DistrictDriveCache).count() == 0


def test_maps_failure_falls_back_to_haversine_and_is_not_cached(db):
    class Boom:
        def drive_minutes(self, *a): raise RuntimeError("quota")
    bm(db, "النرجس", 24.84, 46.65); bm(db, "الياسمين", 24.82, 46.64); db.commit()
    groups, _ = group_bookmarks(db, Boom())
    assert len(groups) == 1 and db.query(DistrictDriveCache).count() == 0


def test_no_route_is_cached_and_not_merged(db):
    class NoRoute:
        calls = 0
        def drive_minutes(self, o, d, dep):
            self.calls += 1
            return [None] * len(d)
    g = NoRoute()
    bm(db, "النرجس", 24.84, 46.65); bm(db, "الياسمين", 24.82, 46.64); db.commit()
    assert len(group_bookmarks(db, g)[0]) == 2 and len(group_bookmarks(db, g)[0]) == 2 and g.calls == 1


def test_no_district_listing_is_its_own_group_and_sort_order(db):
    a = bm(db, None, 24.84, 46.65, score=80)
    bm(db, "الشفا", 24.55, 46.70, score=40); bm(db, "الشفا", 24.551, 46.701, score=50)
    db.commit()
    groups, _ = group_bookmarks(db, None)
    assert groups[0].districts == ["الشفا"] and groups[0].count == 2 and groups[0].avg_score == 45
    g = groups[1]
    assert g.key == f"listing:{a.id}" and g.districts == ["بدون حي"] and g.listing_ids == [a.id]


def test_removed_and_merged_listings_are_excluded(db):
    keep = bm(db, "النرجس", 24.84, 46.65)
    gone = bm(db, "النرجس", 24.84, 46.65); gone.status = "removed"
    dup = bm(db, "النرجس", 24.84, 46.65); dup.merged_into_id = keep.id
    db.commit()
    groups, no_coords = group_bookmarks(db, None)
    assert groups[0].listing_ids == [keep.id] and no_coords == []
