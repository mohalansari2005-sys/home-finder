import re

_LETTERS = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ة": "ه", "ى": "ي", "ؤ": "و", "ئ": "ي"})
_DIACRITICS = re.compile(r"[ً-ْٰـ]")
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩٫٬", "0123456789.,")


def to_western_digits(s: str) -> str:
    return s.translate(_DIGITS)


def normalize_ar(s: str | None) -> str:
    s = _DIACRITICS.sub("", s or "")
    s = s.translate(_LETTERS)
    return re.sub(r"\s+", " ", s).strip()


def normalize_district(s: str | None) -> str:
    return re.sub(r"^حي\s+", "", normalize_ar(s))
