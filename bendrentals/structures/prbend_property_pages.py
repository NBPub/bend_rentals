"""Field extraction for Preferred Residential (prbend.com).

A WordPress site whose property pages carry labelled fields:

    $3,695.00 Per Month | 3 Beds | 2.5 Baths | 2554 Sq Ft
    City: Bend  Date Available: August 1, 2026  Property Type: Single Family

Like AppFolio this produces fields directly, so it is registered with
`title_format = "structured"`. Unlike AppFolio the values are spread across
detail pages, so this module exposes `find_listing_urls` + `parse_detail_fields`.

**This site does not publish street addresses.** The only street address on a
property page is the agency's own office, pulled in by the footer map widget.
Using it would place every listing at one false coordinate, so `address` is
deliberately "?" here.
"""

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..dates import parse_available
from ..extract import cats_allowed_from_text, dogs_allowed_from_text
from ..models import UNKNOWN
from ..place import region_of

#: This site publishes no street address, so a missing one is not a parse
#: failure. See the module docstring.
OMITTED_FIELDS = frozenset({"address"})

#: Field holding a short link that resolves to a Google Maps place URL, from
#: which an address and coordinates can be read. Resolved by the scraper.
MAP_LINK_FIELD = "map_link"

#: A listing URL has a slug; https://prbend.com/property/ is the archive page.
LISTING_HREF_RE = re.compile(r"/property/[^/]+/?$")

PET_RE = re.compile(r"\b(pets?|cats?|dogs?)\b", re.IGNORECASE)
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

DESCRIPTION_HEADING = "About this Property"
AMENITIES_HEADING = "Amenities"


def _clean(node) -> str:
    return re.sub(r"\s+", " ", node.get_text(" ")).strip() if node else ""


def _number(text: str):
    digits = re.sub(r"[^\d]", "", (text or "").split(".")[0])
    return int(digits) if digits else UNKNOWN


def find_listing_urls(index_html: str, base_url: str) -> list[str]:
    """Absolute URLs of the properties linked from the long-term rentals page."""
    soup = BeautifulSoup(index_html, "html.parser")
    urls = []
    for anchor in soup.select("a[href*='/property/']"):
        url = urljoin(base_url, anchor["href"])
        if LISTING_HREF_RE.search(url) and url not in urls:
            urls.append(url)
    return urls


def _key_details(soup) -> dict:
    """The `<value><label>` pairs in the Property Details panel."""
    details = {}
    for block in soup.select(".key-detail"):
        parts = [_clean(child) for child in block.find_all(recursive=False)]
        if len(parts) >= 2:
            details[parts[1].lower()] = parts[0]
    return details


def _bottom_items(soup) -> dict:
    """The `Label: value` rows beneath the panel."""
    items = {}
    for block in soup.select(".bottom-item"):
        text = _clean(block)
        if ":" in text:
            label, _, value = text.partition(":")
            items[label.strip().lower()] = value.strip()
    return items


def _description(soup) -> str:
    """Body text following the "About this Property" heading.

    Bounded to the content column that holds the heading. Walking the whole
    document instead swept in the page footer, which put the agency's postal
    address and phone number into the description.
    """
    heading = soup.find(string=re.compile(DESCRIPTION_HEADING))
    if heading is None:
        return UNKNOWN

    column = heading.find_parent(class_=re.compile(r"et_pb_column"))
    if column is None:
        return UNKNOWN

    # The amenities checklist follows the prose. It is spread across p, li and
    # span tags, so the heading is the only reliable boundary.
    after_amenities = set()
    amenities = soup.find(string=re.compile(AMENITIES_HEADING))
    if amenities is not None:
        after_amenities = {id(node) for node in amenities.parent.find_all_next(["p", "li"])}
        after_amenities.add(id(amenities.parent))

    parts = []
    for node in heading.parent.find_all_next(["p", "li"]):
        if node not in column.descendants:
            break  # left the description column - everything after is chrome
        if id(node) in after_amenities:
            break  # reached the amenities checklist
        text = _clean(node)
        if text and text not in parts:
            parts.append(text)
    return " ".join(parts) if parts else UNKNOWN


def _pets(description: str) -> str:
    sentences = [s.strip() for s in SENTENCE_SPLIT_RE.split(description or "")
                 if PET_RE.search(s)]
    return " ".join(sentences) if sentences else UNKNOWN


def parse_detail_fields(detail_html: str) -> dict:
    """Turn one property page into a field dict."""
    soup = BeautifulSoup(detail_html, "html.parser")

    title = _clean(soup.select_one("h1.property-title")) or UNKNOWN
    details = _key_details(soup)
    bottom = _bottom_items(soup)

    region = region_of(bottom.get("city", ""), title)

    available, available_now = parse_available(bottom.get("date available", ""))
    baths = details.get("baths", "")
    description = _description(soup)
    pets_raw = _pets(description)

    map_link = soup.select_one("a[href*='maps.app.goo.gl'], a[href*='goo.gl/maps']")

    return {
        "link": UNKNOWN,  # filled in by the caller, which knows the URL
        # The site publishes no address, but its "View This Rental on a Map"
        # button links to one. The caller resolves this; see MAP_LINK_FIELD.
        "map_link": map_link["href"] if map_link else UNKNOWN,
        # This site publishes no street address — see the module docstring.
        "address": UNKNOWN,
        "region": region,
        "price": _number(details.get("per month", "")),
        "bedrooms": _number(details.get("beds", "")),
        "bathrooms": baths or UNKNOWN,
        "sqft": _number(details.get("sq ft", "")),
        "available": available,
        "available_now": available_now,
        "cats_allowed": cats_allowed_from_text(pets_raw),
        "dogs_allowed": dogs_allowed_from_text(pets_raw),
        # The only source in the registry that states one: "Single Family",
        # "Condo", and so on. filters.py reads it.
        "property_type": bottom.get("property type", "") or UNKNOWN,
        "summary": title,
        "pets_raw": pets_raw,
    }
