from homefinder.models import Listing
from homefinder.worker.ingest import set_location


def ensure_location(google, listing: Listing) -> None:
    if listing.lat is not None or google is None or not listing.district:
        return
    city = listing.city or "الرياض"
    hit = google.geocode(f"حي {listing.district}، {city}، السعودية")
    if hit:
        set_location(listing, hit[0], hit[1], "district")
