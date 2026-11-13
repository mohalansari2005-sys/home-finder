FIND_QUERY = """
query findListings($size: Int, $from: Int, $sort: SortInput, $where: WhereInput) {
  Web { find(size: $size, from: $from, sort: $sort, where: $where) {
    total
    listings {
      id category price area age beds wc livings street_width street_direction
      maid driver backyard lift furnished duplex blur location_circle_radius
      location { lat lng }
      imgs content title address district direction city path uri create_time last_update status
      deed_number ad_license_number
      user { phone name }
      extended_details { internal_area external_area }
    }
  } }
}
"""

# By-id lookup (see docs/sources/aqar.md). `extended_details` is NOT a field of WebListing, so villa built area is absent here.
LISTING_QUERY = """
query getListing($id: Int!) {
  Web { listing(id: $id) {
    id category price area age beds wc livings street_width street_direction
    maid driver backyard lift furnished duplex blur location_circle_radius
    location { lat lng }
    imgs content title address district direction city path uri create_time last_update status
    deed_number ad_license_number
    user { phone name }
    published
  } }
}
"""

DISTRICTS_QUERY = """
query getAllDistricts($category: Int!, $city_id: Int!, $direction_id: Int) {
  Web { districts(category: $category, city_id: $city_id, direction_id: $direction_id) {
    name district_id count
  } }
}
"""


def find_body(offset: int, where: dict, size: int = 20) -> dict:
    return {"operationName": "findListings", "query": FIND_QUERY,
            "variables": {"size": size, "from": offset, "sort": {"create_time": "desc", "has_img": "desc"}, "where": where}}


def districts_body(category: int, city_id: int) -> dict:
    return {"operationName": "getAllDistricts", "query": DISTRICTS_QUERY,
            "variables": {"category": category, "city_id": city_id}}


def listing_body(listing_id: int) -> dict:
    return {"operationName": "getListing", "query": LISTING_QUERY, "variables": {"id": listing_id}}
