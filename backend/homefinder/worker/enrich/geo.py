from homefinder.models import Listing
from homefinder.worker.ingest import set_location


def ensure_location(maps, listing: Listing) -> None:
    if listing.lat is not None or maps is None or not listing.district:
        return
    city = listing.city or "الرياض"
    hit = maps.geocode(f"حي {listing.district}، {city}، السعودية")
    if hit:
        set_location(listing, hit[0], hit[1], "district")
