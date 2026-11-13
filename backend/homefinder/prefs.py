from sqlalchemy.orm import Session

from homefinder.models import Preferences

DEFAULT_HARD_FILTERS = {"city": "الرياض", "property_types": ["villa"], "districts": [], "price_max": None,
                        "min_bedrooms": None, "max_commute": {}, "building_age_max": None, "street_width_min": None}


def get_or_create(s: Session) -> Preferences:
    p = s.get(Preferences, 1)
    if p is None:
        p = Preferences(id=1, hard_filters=dict(DEFAULT_HARD_FILTERS), weights={}, targets={}, locked_weights=[])
        s.add(p)
        s.flush()
    return p
