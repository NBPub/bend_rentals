"""Field extraction for AppFolio tenant listing pages.

`https://<tenant>.appfolio.com/listings` is server-rendered and puts every field
we need on the index card, so there are no detail-page requests at all.

Unlike squarespace_portfolio, this module produces fields directly rather than a
title string to be parsed — AppFolio has no title convention to decode. Sites
using it are registered with `title_format = "structured"`.

Stable hooks are the `js-listing-*` classes, which exist for scripting rather
than styling and so are less likely to churn than presentational class names.
"""

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..dates import parse_available
from ..extract import cats_allowed_from_text, dogs_allowed_from_text
from ..models import UNKNOWN
from ..place import city_of, region_of

CARD = ".listing-item"
DETAIL_LINK = "a[href*='/listings/detail/']"

#: AppFolio publishes no property type, so its absence is not a parse failure.
OMITTED_FIELDS = frozenset({"property_type"})

#: "3 bd / 2.5 ba", "Studio / 1 ba"
BED_BATH_RE = re.compile(r"(?:(\d+)\s*bd|studio)\s*/\s*([\d.]+)\s*ba", re.IGNORECASE)
PRICE_RE = re.compile(r"\$\s*([\d,]+)")
SQFT_RE = re.compile(r"([\d,]+)")


def _text(node, selector: str) -> str:
    found = node.select_one(selector)
    return re.sub(r"\s+", " ", found.get_text(" ")).strip() if found else ""


def _number(value: str):
    return int(value.replace(",", "")) if value else UNKNOWN


def _normalise_baths(value: str) -> str:
    number = float(value)
    return str(int(number)) if number == int(number) else str(number)


def _parse_card(card, base_url: str) -> dict:
    link = card.select_one(DETAIL_LINK)
    bed_bath = BED_BATH_RE.search(_text(card, ".js-listing-blurb-bed-bath"))
    price = PRICE_RE.search(_text(card, ".js-listing-blurb-rent"))
    sqft = SQFT_RE.search(_text(card, ".js-listing-square-feet"))
    available, available_now = parse_available(_text(card, ".js-listing-available"))

    address = _text(card, ".js-listing-address")
    summary = _text(card, ".js-listing-title")
    pets_raw = re.sub(r"^Pet Policy:\s*", "", _text(card, ".js-listing-pet-policy")).strip()

    bedrooms = UNKNOWN
    bathrooms = UNKNOWN
    if bed_bath:
        # A studio matches the pattern with no digit group — that is 0 bedrooms.
        bedrooms = int(bed_bath.group(1)) if bed_bath.group(1) else 0
        bathrooms = _normalise_baths(bed_bath.group(2))

    return {
        "link": urljoin(base_url, link["href"]) if link else UNKNOWN,
        "address": address or UNKNOWN,
        "region": region_of(city_of(address), summary, address),
        "price": _number(price.group(1)) if price else UNKNOWN,
        "bedrooms": bedrooms,
        "bathrooms": bathrooms,
        "sqft": _number(sqft.group(1)) if sqft else UNKNOWN,
        "available": available,
        "available_now": available_now,
        "cats_allowed": cats_allowed_from_text(pets_raw),
        "dogs_allowed": dogs_allowed_from_text(pets_raw),
        # AppFolio's rental module lists residences only, and publishes no
        # property-type field to confirm it. See structures/OMITTED_FIELDS.
        "property_type": UNKNOWN,
        "summary": summary or UNKNOWN,
        "pets_raw": pets_raw or UNKNOWN,
    }


def parse_index(index_html: str, base_url: str) -> list[dict]:
    """Every listing on an AppFolio index page, as field dicts."""
    soup = BeautifulSoup(index_html, "html.parser")
    return [_parse_card(card, base_url) for card in soup.select(CARD)]
