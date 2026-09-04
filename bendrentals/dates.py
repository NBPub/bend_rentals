"""Normalising the four availability formats our sources publish.

    AppFolio               "9/15/26"  or  "NOW"
    Buildium               "Available 10/20/2026"
    Preferred Residential  "August 1, 2026"
    Rentvine               "2026-10-01"

Immediate availability is kept out of the date column: `available` holds a real
ISO date or "?", and `available_now` carries the True/False flag. Writing
today's date for "NOW" would invent a fact and would change on every run.
"""

import re
from datetime import date, datetime

from .models import UNKNOWN

#: Wording sources use for "you can move in immediately".
NOW_RE = re.compile(r"\b(now|immediately|available\s+now|today)\b", re.IGNORECASE)

#: Two-digit years below this are 20xx. Leases are not written 70 years out.
CENTURY_PIVOT = 70

_NUMERIC_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b")
_ISO_RE = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
_MONTH_NAME_FORMATS = ("%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y")


def _iso(year: int, month: int, day: int) -> str | None:
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def parse_available(text: str) -> tuple[str, str]:
    """Return (ISO date or "?", available_now as "True"/"False"/"?").

    A source that says nothing yields ("?", "?"): silence is not a claim that
    the place is unavailable.
    """
    if not text or text == UNKNOWN:
        return UNKNOWN, UNKNOWN

    cleaned = re.sub(r"^\s*Available[:\s]*", "", str(text).strip(), flags=re.IGNORECASE)
    if not cleaned:
        return UNKNOWN, UNKNOWN

    iso = _ISO_RE.search(cleaned)
    if iso:
        found = _iso(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        if found:
            return found, "False"

    numeric = _NUMERIC_RE.search(cleaned)
    if numeric:
        month, day, year = (int(part) for part in numeric.groups())
        if year < 100:
            year += 2000 if year < CENTURY_PIVOT else 1900
        found = _iso(year, month, day)
        if found:
            return found, "False"

    for fmt in _MONTH_NAME_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).date().isoformat(), "False"
        except ValueError:
            continue

    # Only after every date shape has failed: a bare "NOW" and nothing else.
    if NOW_RE.search(cleaned):
        return UNKNOWN, "True"

    return UNKNOWN, UNKNOWN
