"""Reading a city and a Bend quadrant out of an address.

Every structure module needs this, and four of them had grown their own copy —
with two subtly different city patterns, one of which silently failed on
addresses written "Bend OR 97702" rather than "Bend, OR 97702".
"""

import re

from .models import UNKNOWN

#: Handles both "…, Bend OR 97702" and "…, Bend, OR 97703".
CITY_RE = re.compile(r",\s*([A-Za-z][A-Za-z .]*?)\s*,?\s*[A-Z]{2}\s+\d{5}")

#: Bend's compass quadrants. "Northwest" spelled out is deliberately not
#: matched: it appears in neighbourhood names that do not imply a location.
QUADRANT_RE = re.compile(r"\b(NE|NW|SE|SW)\b")


def city_of(address: str) -> str:
    """City named in an address, or "?" if it cannot be read."""
    if not address or address == UNKNOWN:
        return UNKNOWN
    match = CITY_RE.search(address)
    return match.group(1).strip() if match else UNKNOWN


def region_of(city: str, *texts: str) -> str:
    """"SW Bend" where a quadrant appears in `texts`, else the city, else "?".

    `texts` are searched in order, so pass the most authoritative first.
    """
    city_name = "" if not city or city == UNKNOWN else city.strip()
    for text in texts:
        if not text or text == UNKNOWN:
            continue
        quadrant = QUADRANT_RE.search(text)
        if quadrant and city_name:
            return f"{quadrant.group(1)} {city_name}"
    return city_name or UNKNOWN
