from datetime import datetime
from urllib.parse import parse_qs, unquote, urlparse

from homefinder.server.visits.links import google_maps_directions, normalize_sa_mobile, whatsapp_link


def test_whatsapp_phone_normalization():
    for raw in ["0551234567", "+966 55 123 4567", "966551234567", "551234567", "٠٥٥١٢٣٤٥٦٧",
                "00966551234567", "966-55-123-4567", "9660551234567"]:
        assert normalize_sa_mobile(raw) == "966551234567", raw
    for bad in ["0112345678", "12345", "", None, "abc", "966112345678", "0451234567", "05512345678"]:
        assert normalize_sa_mobile(bad) is None, bad


def test_whatsapp_message_contains_title_day_and_time():
    url = whatsapp_link("0551234567", "فيلا درج داخلي", datetime(2026, 11, 21, 16, 20))
    assert url.startswith("https://wa.me/966551234567?text=")
    text = unquote(url.split("text=")[1])
    assert "فيلا درج داخلي" in text and "السبت" in text and "4:20" in text and "مساءً" in text
    assert whatsapp_link("0112345678", "x", None) is None


def test_whatsapp_message_leaks_nothing_else():
    text = unquote(whatsapp_link("0551234567", "فيلا", datetime(2026, 11, 21, 9, 5)).split("text=")[1])
    assert text == 'السلام عليكم، شفت إعلانكم "فيلا" وحاب أزوره يوم السبت الساعة 9:05 صباحاً، هل يناسبكم؟'
    no_title = unquote(whatsapp_link("0551234567", None, None).split("text=")[1])
    assert "None" not in no_title and "يوم" not in no_title


def test_google_maps_directions_go_to_one_stop_from_the_phone():
    url = google_maps_directions(24.8, 46.61)
    assert url.startswith("https://www.google.com/maps/dir/?")
    q = parse_qs(urlparse(url).query)
    assert q == {"api": ["1"], "destination": ["24.8,46.61"], "travelmode": ["driving"]}
    assert google_maps_directions(None, 46.61) is None
