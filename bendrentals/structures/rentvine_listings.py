"""Field extraction for Rentvine-hosted sites (*.rentvine.com).

The public website renders its vacancies with a JavaScript widget, so the page
itself contains no listings. The widget reads
`https://<tenant>.rentvine.com/api/public/listings`, which returns JSON — the
same data the public page displays, from the endpoint the public page uses.

That JSON is richer than any HTML source in this project. It carries an explicit
`acceptCats` boolean and, uniquely, **latitude and longitude**, so Rentvine
listings need no geocoding at all.

Note the JSON here is nothing like Squarespace's `?format=json`, which robots.txt
disallows: this is the widget's own documented data path, and Rentvine publishes
no robots.txt (both hosts return 403).

The response also includes agent names, phone numbers and email addresses. Those
are third-party contact details we have no use for and are deliberately dropped.
"""

import json
import re

from ..dates import parse_available
from ..models import UNKNOWN
from ..place import region_of

#: Client-side route for a single listing on the tenant's public site.
#:
#: The public app answers every path with the same shell, so this cannot be
#: verified by fetching it. The route is declared in the app's own bundle as
#: `/listings/:id([0-9]+)`, under the `/public/` mount.
LISTING_PATH = "/public/listings/{listing_id}"

#: Which id fills that route, most specific first. `propertyListingID` is the
#: listing's own id and matches the route's name; `unitID` is the fallback,
#: and is what the API's own `applicationUrl` uses. Every listing published so
#: far carries the same value for both, so this changes no link today.
LISTING_ID_KEYS = ("propertyListingID", "unitID")

#: See the property_type note in parse_index.
OMITTED_FIELDS = frozenset({"property_type"})



def _text(value) -> str:
    if value is None:
        return UNKNOWN
    text = str(value).strip()
    return text or UNKNOWN


def _number(value):
    if value is None:
        return UNKNOWN
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return UNKNOWN


def _baths(unit: dict) -> str:
    """Prefer the combined figure; fall back to full + half."""
    for key in ("baths", "fullBaths"):
        value = unit.get(key)
        if value is not None:
            number = float(value)
            if key == "fullBaths" and unit.get("halfBaths"):
                number += 0.5 * float(unit["halfBaths"])
            return str(int(number)) if number == int(number) else str(number)
    return UNKNOWN


def _accepts(listing: dict, key: str) -> str:
    """Rentvine's own boolean, which arrives as 1/0 or "1"/"0"."""
    accepts = listing.get(key)
    if accepts in (1, True, "1"):
        return "True"
    if accepts in (0, False, "0"):
        return "False"
    return UNKNOWN


def _listing_id(unit: dict, listing: dict):
    """The id for the public listing route, or None if the payload has none."""
    for key in LISTING_ID_KEYS:
        for source in (listing, unit):
            value = source.get(key)
            if value not in (None, ""):
                return value
    return None


def _address(unit: dict) -> str:
    street = (unit.get("address") or "").strip()
    if not street:
        return UNKNOWN
    parts = [street]
    if unit.get("address2"):
        parts.append(str(unit["address2"]).strip())
    tail = " ".join(
        str(unit.get(key) or "").strip() for key in ("stateID", "postalCode")
    ).strip()
    city = (unit.get("city") or "").strip()
    if city:
        parts.append(f"{city}, {tail}".strip().rstrip(","))
    return ", ".join(parts)


def _base_host(base_url: str) -> str:
    return base_url.split("/api/", 1)[0].rstrip("/")


def parse_index(index_json: str, base_url: str) -> list[dict]:
    """Every listing in the widget's JSON payload, as field dicts."""
    try:
        payload = json.loads(index_json)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []

    host = _base_host(base_url)
    rows = []
    for record in payload:
        unit = record.get("unit") or {}
        listing = record.get("listing") or {}

        address = _address(unit)
        city = (unit.get("city") or "").strip()
        headline = _text(listing.get("headline"))
        region = region_of(city, address, headline)

        listing_id = _listing_id(unit, listing)
        pets = _text(listing.get("petDescription"))
        available, available_now = parse_available(listing.get("availabilityDate"))

        rows.append({
            "link": (host + LISTING_PATH.format(listing_id=listing_id)
                     if listing_id else UNKNOWN),
            "address": address,
            "region": region,
            "price": _number(unit.get("rent") or unit.get("marketRent")),
            "bedrooms": _number(unit.get("beds")),
            "bathrooms": _baths(unit),
            "sqft": _number(unit.get("size") or listing.get("size")),
            "available": available,
            "available_now": available_now,
            "cats_allowed": _accepts(listing, "acceptCats"),
            "dogs_allowed": _accepts(listing, "acceptDogs"),
            # propertyTypeID is an opaque integer with no published key, so it
            # cannot be turned into a type name we would be willing to filter on.
            "property_type": UNKNOWN,
            "summary": headline,
            "pets_raw": pets,
            # Rentvine publishes coordinates, so these skip geocoding entirely.
            "lat": _text(unit.get("latitude")),
            "lon": _text(unit.get("longitude")),
        })
    return rows
